from starknet_py.contract import Contract
from starknet_py.hash.address import compute_address
from starknet_py.net.account.account import Account
from starknet_py.net.client_errors import ClientError
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.models import StarknetChainId
from starknet_py.net.signer.stark_curve_signer import KeyPair
from starknet_py.net.account.account import Account, _parse_calls_v2, _execute_payload_serializer_v2, _execute_payload_serializer, _merge_calls
from starknet_py.utils.iterable import ensure_iterable
from starknet_py.net.models import Invoke
from config import settings
import requests
from utils import retry, print
from json import load
import aiohttp
import asyncio
from eth_utils import to_wei
from random import randrange
import questionary
import sys


with open("abis/erc20.json", "r") as f:
    ERC20_ABI = load(f)


with open("abis/claim.json", "r") as f:
    CLAIM_ABI = load(f)


with open("abis/strk.json", "r") as f:
    STRK_ABI = load(f)


PROOFS = dict()


def get_address(key_pair=None, private_key=None):
    """
    Retrieves the Ethereum address associated with the provided key pair or private key.

    Parameters:
    - key_pair: Starknet key pair (default: None)
    - private_key: Private key in integer format (default: None)

    Returns:
    - int: Ethereum address in integer format
    """
    if not key_pair:
        key_pair = KeyPair.from_private_key(private_key)
    res = requests.get(
        f'https://recovery.braavos.app/pubkey-to-address/?network=mainnet-alpha&pubkey={hex(key_pair.public_key)}'
    )
    if res.status_code == 200:
        addresses = res.json()['address']
        if len(addresses) > 0:
            return int(addresses[0], 16)
    return compute_address(
        class_hash=settings.ARGENTX_IMPLEMENTATION_CLASS_HASH,
        constructor_calldata=[key_pair.public_key, 0],
        salt=key_pair.public_key,
    )


def get_account(key_pair=None, private_key=None, session=None):
    """
    Creates a Starknet account using the provided key pair or private key.

    Parameters:
    - key_pair: Starknet key pair (default: None)
    - private_key: Private key in integer format (default: None)
    - session: Aiohttp client session (default: None)

    Returns:
    - Account: Starknet account
    """
    if not key_pair:
        key_pair = KeyPair.from_private_key(private_key)
    return Account(
        address=get_address(key_pair=key_pair, private_key=private_key),
        client=FullNodeClient(
            settings.STARKNET_RPC,
            session=session
        ),
        key_pair=key_pair,
        chain=StarknetChainId.MAINNET,
    )


async def get_balance(starknet_account):
    """
    Retrieves the balance of the Starknet account in ETH.

    Parameters:
    - starknet_account: Starknet account instance

    Returns:
    - float: Balance in ETH
    """
    return (await Contract(
        address=settings.ETH_ADDRESS,
        abi=ERC20_ABI,
        provider=starknet_account
    ).functions["balanceOf"].call(starknet_account.address)).balance


async def is_deployed(starknet_account):
    """
    Checks if the Starknet account is deployed.

    Parameters:
    - starknet_account: Starknet account instance

    Returns:
    - bool: True if deployed, False otherwise
    """
    try:
        await starknet_account.get_nonce()
        return True
    except ClientError:
        return False


# @check_gas
# @retry
async def claim(starknet_account, proof, cex_address):
    """
    Claims STRK tokens and transfers them to the specified address.

    Parameters:
    - starknet_account: Starknet account instance
    - proof: Proof data for the claim
    - cex_address: Address to transfer STRK tokens to

    Returns:
    - str: Transaction hash in hexadecimal format
    """
    amount, index, path = to_wei(proof["amount"], 'ether'), proof["index"], proof["path"]

    tx = (await starknet_account.client.send_transaction(await starknet_account.sign_invoke_transaction(
        calls=[
            Contract(
                address=settings.CLAIM_ADDRESS,
                abi=CLAIM_ABI,
                provider=starknet_account,
                cairo_version=1
            ).functions["claim"].prepare({
                "identity": starknet_account.address,
                "balance": amount,
                "index": index,
                "merkle_path": path
            }),
            Contract(
                address=settings.STRK_ADDRESS,
                abi=STRK_ABI,
                provider=starknet_account,
                cairo_version=1
            ).functions["transfer"].prepare(
                cex_address,
                amount
            )
        ],
        auto_estimate=True,
        nonce=(await starknet_account.get_nonce())
    ))).transaction_hash

    await starknet_account.client.wait_for_tx(tx, check_interval=10)

    return hex(tx)


async def claim_and_transfer(private_key, transfer_address):
    """
    Claims STRK tokens and transfers them for multiple wallets.

    Parameters:
    - private_key: Private key in integer format
    - transfer_address: Address to transfer STRK tokens to

    Returns:
    - None
    """
    aio_session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    )

    starknet_account = get_account(private_key=private_key, session=aio_session)

    print(f"Address: {hex(starknet_account.address)}")

    if not (await is_deployed(starknet_account)):
        print('not deployed')
    else:
        print('deployed')

    balance = await get_balance(starknet_account)
    print(f'Account has {format(balance / 10**18, "0.18f")} ETH')

    proof = PROOFS.get(hex(starknet_account.address), None)

    if proof:
        print(f"Address {hex(starknet_account.address)} found in proofs, claiming {proof['amount']} STRK and transferring to {hex(transfer_address)}")
        try:
            tx = await claim(starknet_account, proof, transfer_address)
            print(f"Address claimed. Transaction URL: {settings.EXPLORER_URL}/{tx}")
        except Exception as e:
            print(f"Error while claiming and transferring: {e}")

    else:
        print('Address not found in proofs')

    await aio_session.close()

    sleep_account = randrange(*settings.ACCOUNT_WAIT)
    print(f"Sleeping for {sleep_account} seconds...")
    await asyncio.sleep(sleep_account)


async def get_fee(starknet_account, calls):
    """
    Estimates the transaction fee for transferring ETH.

    Parameters:
    - starknet_account: Starknet account instance
    - address_to: Address to transfer ETH to
    - amount: Amount of ETH to transfer

    Returns:
    - float: Estimated transaction fee
    """
    if await starknet_account.cairo_version == 1:
        wrapped_calldata = _execute_payload_serializer_v2.serialize(
            {
                "calls": _parse_calls_v2(ensure_iterable(calls))
            }
        )
    else:
        call_descriptions, calldata = _merge_calls(ensure_iterable(calls))
        wrapped_calldata = _execute_payload_serializer.serialize(
            {
                "call_array": call_descriptions,
                "calldata": calldata
            }
        )

    return await starknet_account._get_max_fee(Invoke(
        calldata=wrapped_calldata,
        signature=[],
        max_fee=0,
        version=1,
        nonce=await starknet_account.get_nonce(),
        sender_address=starknet_account.address,
    ), auto_estimate=True)


async def transfer(starknet_account, address_to, amount):
    """
    Transfers ETH to the specified address.

    Parameters:
    - starknet_account: Starknet account instance
    - address_to: Address to transfer ETH to
    - amount: Amount of ETH to transfer

    Returns:
    - str: Transaction hash in hexadecimal format
    """
    if amount == 0:
        print("Skipping...")
        return
    
    transfer_function = Contract(
        address=settings.ETH_ADDRESS,
        abi=ERC20_ABI,
        provider=starknet_account
    ).functions['transfer']

    max_fee = await get_fee(starknet_account, [
        transfer_function.prepare(address_to, amount),
    ])

    if not max_fee:
        print("Can't estimate fee, skipping...")
        return
    
    print(f"Max fee: {format(max_fee / 10**18, '0.18f')} ETH")
    
    amount -= max_fee
    
    if amount <= 0:
        print("Amount too low, skipping...")
        return

    print("Transferring...")

    tx = (await starknet_account.client.send_transaction(await starknet_account.sign_invoke_transaction(
        calls=[
            transfer_function.prepare(address_to, amount - max_fee),
        ],
        auto_estimate=True,
        nonce=(await starknet_account.get_nonce())
    ))).transaction_hash

    await starknet_account.client.wait_for_tx(tx, check_interval=10)

    return hex(tx)


async def withdraw_eth(private_key, transfer_address):
    """
    Withdraws ETH from the Starknet account.

    Parameters:
    - private_key: Private key in integer format
    - transfer_address: Address to transfer ETH to

    Returns:
    - None
    """
    aio_session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    )

    starknet_account = get_account(private_key=private_key, session=aio_session)

    print(f"Address: {hex(starknet_account.address)}")

    if not (await is_deployed(starknet_account)):
        print('not deployed')
    else:
        print('deployed')

    balance = await get_balance(starknet_account)
    print(f'Account has {format(balance / 10**18, "0.18f")} ETH')

    try:
        tx = await transfer(starknet_account, transfer_address, balance)
        print(f"ETH successfully withdrawn. Transaction URL: {settings.EXPLORER_URL}/{tx}")
    except Exception as e:
        print(f"Error while withdrawing: {e}")
        
    balance = await get_balance(starknet_account)
    print(f'Account after transfer has {format(balance / 10**18, "0.18f")} ETH')

    await aio_session.close()

    sleep_account = randrange(*settings.ACCOUNT_WAIT)
    print(f"Sleeping for {sleep_account} seconds...")
    await asyncio.sleep(sleep_account)


def load_proofs():
    """
    Loads proofs from files and updates the PROOFS dictionary.

    Returns:
    - None
    """
    global PROOFS
    print("Loading PROOFS lists...")
    for i in range(11):
        with open(f"proofs/starknet-{i}.json", "r") as f:
            PROOFS.update(load(f))
    print("PROOFS loaded")


def load_privkeys():
    """
    Loads private keys from the 'privkeys.txt' file.

    Returns:
    - list: List of private key strings
    """
    with open('privkeys.txt', 'r') as f:
        privkeys = f.readlines()

    return list(filter(lambda x: x[0] != '#' if x else '', privkeys))


def run_wallets():
    """
    Runs the claiming and transferring process for multiple wallet pairs.

    Returns:
    - None
    """
    privkeys = load_privkeys()

    n = len(privkeys)

    if n == 0:
        print('No private keys found')
        return

    print(f"Found {n} private keys")
    print("Running...")

    for i in range(n):
        print(f"Wallet pair {i + 1}/{n}")

        try:
            private_key, transfer_address = map(lambda x: int(x, 16), privkeys[i].split(":"))
        except Exception as e:
            print(f"Not a valid private key pair: {privkeys[i]}")
            print(e)
            print("Skipping...")

        try:
            asyncio.run(claim_and_transfer(private_key, transfer_address))
        except Exception as e:
            print(f"Error while claiming and transferring: {e}")
            print("Continuing...")


def withdraw_wallets():
    """
    Withdraws ETH from multiple wallet pairs.

    Returns:
    - None
    """
    privkeys = load_privkeys()

    n = len(privkeys)

    if n == 0:
        print('No private keys found')
        return

    print(f"Found {n} private keys")
    print("Running...")

    for i in range(n):
        print(f"Wallet pair {i + 1}/{n}")

        try:
            private_key, transfer_address = map(lambda x: int(x, 16), privkeys[i].split(":"))
        except Exception as e:
            print(f"Not a valid private key pair: {privkeys[i]}")
            print(e)
            print("Skipping...")

        try:
            asyncio.run(withdraw_eth(private_key, transfer_address))
        except Exception as e:
            print(f"Error while claiming and transferring: {e}")
            print("Continuing...")


def main():
    """
    Main method to interactively choose and execute actions.

    Returns:
    - None
    """
    res = questionary.select(
            "ACTION: (please go to README.md before doing anything)",
            choices=[
                questionary.Choice("1) claim and withdraw STRK", 'claim'),
                questionary.Choice("2) withdraw ETH", 'withdraw'),
                questionary.Choice("3) exit", 'exit'),
            ],
            qmark="",
            pointer="-> ",
        ).ask()
    if res == 'claim':
        load_proofs()
        run_wallets()
    elif res == 'withdraw':
        withdraw_wallets()
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
