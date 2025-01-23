from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict, Tuple
from enum import Enum

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int = None
    API_HASH: str = None
    GLOBAL_CONFIG_PATH: str = "TG_FARM"

    FIX_CERT: bool = False
    CHECK_API_HASH: bool = True
    SESSION_START_DELAY: int = 1080
    
    NIGHT_MODE: bool = False
    NIGHT_TIME: Tuple[int, int] = (0, 7)
    NIGHT_CHECKING: Tuple[int, int] = (10800, 14400)

    BLOCKS_BEFORE_SLEEP: Tuple[int, int] = (1, 120)
    SLEEP_HOURS: Tuple[int, int] = (2, 4)

    REF_ID: str = 'ref_b2434667eb27d01f'
    SESSIONS_PER_PROXY: int = 1
    USE_PROXY: bool = True
    DISABLE_PROXY_REPLACE: bool = False

    DEVICE_PARAMS: bool = False
    
    SUBSCRIBE_TELEGRAM: bool = False
    COMMUNITY_CHANNEL: str = "theopencoin_community"

    JOIN_POOL: bool = False

    DEBUG_LOGGING: bool = False

    AUTO_UPDATE: bool = True
    CHECK_UPDATE_INTERVAL: int = 300
    BLACKLISTED_SESSIONS: str = ""

    DEBUG_HASH: bool = False

    @property
    def blacklisted_sessions(self) -> List[str]:
        return [s.strip() for s in self.BLACKLISTED_SESSIONS.split(',') if s.strip()]

settings = Settings()
