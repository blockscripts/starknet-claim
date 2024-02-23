from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv(".env")


class Settings(BaseSettings):
    STARKNET_RPC: str
    EXPLORER_URL: str = "https://voyager.online/tx"
    ARGENTX_IMPLEMENTATION_CLASS_HASH: int = 0x01a736d6ed154502257f02b1ccdf4d9d1089f80811cd6acad48e6b6a9d1f2003
    CLAIM_ADDRESS: int = 0x06793d9e6ed7182978454c79270e5b14d2655204ba6565ce9b0aa8a3c3121025
    ETH_ADDRESS: int = 0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7
    STRK_ADDRESS: int = 0x04718f5a0fc34cc1af16a1cdee98ffb20c31f5cd61d6ab07201858f4287c938d
    ACCOUNT_WAIT: list[int] = [20, 60]
    MAX_GAS: int = 50 * 10**9
    GAS_WAIT: list[int] = [10, 30]
    RETRY_COUNT: int = 5
    RETRY_WAIT: list[int] = [20, 60]


settings = Settings()
