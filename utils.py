from loguru import logger
from starknet_py.net.gateway_client import GatewayClient
from web3 import Web3
from config import settings
import random
import asyncio
from datetime import datetime
import builtins
import aiohttp


def retry(func):
    """
    A decorator for retrying asynchronous functions.

    Parameters:
    - func: Asynchronous function to be retried

    Returns:
    - function: Wrapper function with retry logic
    """
    async def wrapper(*args, **kwargs):
        retries = 0
        while retries < settings.RETRY_COUNT:
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Error | {e}")
                await asyncio.sleep(random.randrange(*settings.RETRY_WAIT))
                retries += 1

    return wrapper


async def sleep(sleep_from: int, sleep_to: int):
    """
    Asynchronously sleeps for a random duration within the specified range.

    Parameters:
    - sleep_from: Minimum sleep duration in seconds
    - sleep_to: Maximum sleep duration in seconds

    Returns:
    - None
    """
    delay = random.randint(sleep_from, sleep_to)

    logger.info(f"💤 Sleep {delay} s.")
    await asyncio.sleep(delay)


async def wait_gas():
    """
    Waits for the gas price to be within the acceptable range.

    Returns:
    - None
    """
    logger.info("Get GWEI")

    aio_session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    )

    client = GatewayClient("mainnet", aio_session)

    while True:
        block_data = await client.get_block("latest")
        if block_data.gas_price is not None:
            gas = Web3.from_wei(block_data.gas_price, "wei")

            if gas > settings.MAX_GAS:
                logger.info(f'Current GWEI: {gas} > {settings.MAX_GAS}')
                await sleep(*settings.GAS_WAIT)
            else:
                logger.success(f"GWEI is normal | current: {gas} < {settings.MAX_GAS}")
                break
        else:
            logger.error("block_data.gas_price is None")
            await sleep(*settings.GAS_WAIT)

    await aio_session.close()


def check_gas(func):
    """
    A decorator that checks and ensures the gas price is within the acceptable range before executing a function.

    Parameters:
    - func: Asynchronous function to be checked for gas price

    Returns:
    - function: Wrapper function with gas check logic
    """
    async def _wrapper(*args, **kwargs):
        await wait_gas()
        return await func(*args, **kwargs)
    return _wrapper


def print(*args, **kwargs):
    """
    Custom print function that adds a timestamp to each log.

    Parameters:
    - args: Positional arguments for the built-in print function
    - kwargs: Keyword arguments for the built-in print function

    Returns:
    - None
    """
    builtins.print(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], end=" | "
    )
    builtins.print(*args, **kwargs)
