from datetime import datetime
from typing import Optional, Dict, List
import json

from bot.core.tapper import BaseBot
from bot.utils.universal_telegram_client import UniversalTelegramClient
from bot.utils import logger


class OpenCoinMiner(BaseBot):
    def __init__(self, tg_client: UniversalTelegramClient):
        super().__init__(tg_client)
        self._auth_header: Optional[str] = None
        self._base_url = "https://miniapp.theopencoin.xyz/api/v1"
        self._current_block_id: Optional[int] = None
        self._after_block_id: Optional[int] = None

    async def _init_auth_header(self) -> None:
        """Инициализация заголовка авторизации."""
        tg_web_data = await self.get_tg_web_data()
        self._auth_header = f"tma {tg_web_data}"

    async def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков для запросов."""
        if not self._auth_header:
            await self._init_auth_header()
            
        return {
            "accept": "*/*",
            "authorization": self._auth_header,
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }

    async def get_user_stats(self) -> Optional[Dict]:
        """Получение статистики пользователя."""
        headers = await self._get_headers()
        return await self.make_request(
            "GET", 
            f"{self._base_url}/users/stats",
            headers=headers
        )

    async def get_latest_block(self) -> Optional[Dict]:
        """Получение информации о последнем блоке."""
        headers = await self._get_headers()
        return await self.make_request(
            "GET",
            f"{self._base_url}/blocks/latest",
            headers=headers
        )

    async def start_mining(self, block_id: int) -> bool:
        """Начало майнинга блока."""
        headers = await self._get_headers()
        result = await self.make_request(
            "POST",
            f"{self._base_url}/blocks/start-mining",
            headers=headers,
            json={"blockId": block_id}
        )
        return result is not None

    async def get_mining_results(self) -> List[Dict]:
        """Получение результатов майнинга."""
        if not self._current_block_id or not self._after_block_id:
            return []
            
        headers = await self._get_headers()
        return await self.make_request(
            "GET",
            f"{self._base_url}/blocks/user-results?afterBlockId={self._after_block_id}&currentBlockId={self._current_block_id}",
            headers=headers
        ) or []

    async def process_bot_logic(self) -> None:
        """Основная логика майнинга."""
        try:
            # Получаем статистику пользователя
            stats = await self.get_user_stats()
            if stats:
                logger.info(
                    f"{self.session_name} | Mined: {stats['tokensMined']:.6f} OPEN, "
                    f"Referrals: {stats['numberOfReferrals']}"
                )

            # Получаем информацию о последнем блоке
            latest_block = await self.get_latest_block()
            if not latest_block:
                return

            self._current_block_id = latest_block["id"]
            if not self._after_block_id:
                self._after_block_id = self._current_block_id - 1

            # Если не майним, начинаем майнинг
            if not latest_block["isUserMining"]:
                if await self.start_mining(self._current_block_id):
                    logger.info(
                        f"{self.session_name} | Started mining block {self._current_block_id} "
                        f"with {latest_block['minersCount']} miners"
                    )

            # Проверяем результаты
            results = await self.get_mining_results()
            for result in results:
                logger.info(
                    f"{self.session_name} | Mined {result['rewards']:.6f} OPEN "
                    f"from block {result['block_id']}"
                )
                self._after_block_id = max(self._after_block_id, int(result['block_id']))

        except Exception as e:
            logger.error(f"{self.session_name} | Error in mining process: {str(e)}")


async def run_opencoin_miner(tg_client: UniversalTelegramClient):
    """Функция для запуска майнера OpenCoin."""
    miner = OpenCoinMiner(tg_client=tg_client)
    try:
        await miner.run()
    except Exception as e:
        logger.error(f"OpenCoin Miner Error: {str(e)}") 