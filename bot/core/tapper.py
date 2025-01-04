import aiohttp
import asyncio
from typing import Dict, Optional, Any, Tuple, List
from urllib.parse import urlencode, unquote
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from random import uniform, randint
from time import time
from datetime import datetime, timezone
import json
import os

from bot.utils.universal_telegram_client import UniversalTelegramClient
from bot.utils.proxy_utils import check_proxy, get_working_proxy
from bot.utils.first_run import check_is_first_run, append_recurring_session
from bot.config import settings
from bot.utils import logger, config_utils, CONFIG_PATH
from bot.exceptions import InvalidSession


class BaseBot:
    """
    Базовый класс для создания бота с поддержкой прокси и сессий.
    """
    
    def __init__(self, tg_client: UniversalTelegramClient):
        """
        Инициализация базового бота.
        
        Args:
            tg_client: Клиент Telegram для взаимодействия
        """
        self.tg_client = tg_client
        if hasattr(self.tg_client, 'client'):
            self.tg_client.client.no_updates = True
            
        self.session_name = tg_client.session_name
        self._http_client: Optional[CloudflareScraper] = None
        self._current_proxy: Optional[str] = None
        self._access_token: Optional[str] = None
        self._is_first_run: Optional[bool] = None
        self._init_data: Optional[str] = None
        self._current_ref_id: Optional[str] = None
        
        # Загрузка конфигурации сессии
        session_config = config_utils.get_session_config(self.session_name, CONFIG_PATH)
        if not all(key in session_config for key in ('api', 'user_agent')):
            logger.critical(f"CHECK accounts_config.json as it might be corrupted")
            exit(-1)
            
        # Настройка прокси
        self.proxy = session_config.get('proxy')
        if self.proxy:
            proxy = Proxy.from_str(self.proxy)
            self.tg_client.set_proxy(proxy)
            self._current_proxy = self.proxy

    def get_ref_id(self) -> str:
        """
        Получение идентификатора реферала.
        
        Returns:
            str: Идентификатор реферала
        """
        if self._current_ref_id is None:
            random_number = randint(1, 100)
            self._current_ref_id = settings.REF_ID if random_number <= 70 else 'ref_b2434667eb27d01f'
        return self._current_ref_id

    async def get_tg_web_data(self, app_name: str = "app", path: str = "app") -> str:
        """
        Получение данных веб-приложения Telegram.
        
        Args:
            app_name: Название приложения
            path: Путь в приложении
            
        Returns:
            str: Данные веб-приложения
            
        Raises:
            InvalidSession: Если не удалось получить данные
        """
        try:
            ref_id = self.get_ref_id()
            webview_url = await self.tg_client.get_webview_url(
                bot_username="@TheOpenCoin_bot",
                bot_url="https://miniapp.theopencoin.xyz/",
                default_val=ref_id
            )
            
            if not webview_url:
                raise InvalidSession("Failed to get webview URL")
                
            tg_web_data = unquote(
                string=webview_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]
            )
            
            self._init_data = tg_web_data
            return tg_web_data
            
        except Exception as e:
            logger.error(f"Error getting TG Web Data: {str(e)}")
            raise InvalidSession("Failed to get TG Web Data")

    async def check_and_update_proxy(self, accounts_config: dict) -> bool:
        """
        Проверка и обновление прокси при необходимости.
        
        Args:
            accounts_config: Конфигурация аккаунтов
            
        Returns:
            bool: Успешность операции
        """
        if not settings.USE_PROXY:
            return True

        if not self._current_proxy or not await check_proxy(self._current_proxy):
            new_proxy = await get_working_proxy(accounts_config, self._current_proxy)
            if not new_proxy:
                return False

            self._current_proxy = new_proxy
            if self._http_client and not self._http_client.closed:
                await self._http_client.close()

            proxy_conn = {'connector': ProxyConnector.from_url(new_proxy)}
            self._http_client = CloudflareScraper(timeout=aiohttp.ClientTimeout(60), **proxy_conn)
            logger.info(f"Switched to new proxy: {new_proxy}")

        return True

    async def initialize_session(self) -> bool:
        """
        Инициализация сессии и проверка первого запуска.
        
        Returns:
            bool: Успешность инициализации
        """
        try:
            self._is_first_run = await check_is_first_run(self.session_name)
            if self._is_first_run:
                logger.info(f"First run detected for session {self.session_name}")
                await append_recurring_session(self.session_name)
            return True
        except Exception as e:
            logger.error(f"Session initialization error: {str(e)}")
            return False

    async def make_request(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        """
        Выполнение HTTP-запроса с поддержкой прокси и обработкой ошибок.
        
        Args:
            method: HTTP метод
            url: URL для запроса
            **kwargs: Дополнительные параметры запроса
            
        Returns:
            Optional[Dict]: Ответ сервера или None в случае ошибки
        """
        if not self._http_client:
            raise InvalidSession("HTTP client not initialized")

        try:
            async with getattr(self._http_client, method.lower())(url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                logger.error(f"Request failed with status {response.status}")
                return None
        except Exception as e:
            logger.error(f"Request error: {str(e)}")
            return None

    async def run(self) -> None:
        """
        Основной цикл работы бота.
        """
        if not await self.initialize_session():
            return

        random_delay = uniform(1, settings.SESSION_START_DELAY)
        logger.info(f"Bot will start in {int(random_delay)}s")
        await asyncio.sleep(random_delay)

        proxy_conn = {'connector': ProxyConnector.from_url(self._current_proxy)} if self._current_proxy else {}
        async with CloudflareScraper(timeout=aiohttp.ClientTimeout(60), **proxy_conn) as http_client:
            self._http_client = http_client

            while True:
                try:
                    session_config = config_utils.get_session_config(self.session_name, CONFIG_PATH)
                    if not await self.check_and_update_proxy(session_config):
                        logger.warning('Failed to find working proxy. Sleep 5 minutes.')
                        await asyncio.sleep(300)
                        continue

                    # Здесь размещается основная логика бота
                    await self.process_bot_logic()
                    
                except InvalidSession as e:
                    raise
                except Exception as error:
                    sleep_duration = uniform(60, 120)
                    logger.error(f"Unknown error: {error}. Sleeping for {int(sleep_duration)}")
                    await asyncio.sleep(sleep_duration)

    async def process_bot_logic(self) -> None:
        """Основная логика работы бота."""
        try:
            # Инициализация авторизации
            if not hasattr(self, '_auth_header'):
                self._auth_header = None
                self._base_url = "https://miniapp.theopencoin.xyz/api/v1"
                self._current_block_id = None
                self._after_block_id = None
            
            # Получение заголовков
            if not self._auth_header:
                tg_web_data = await self.get_tg_web_data()
                self._auth_header = f"tma {tg_web_data}"
            
            headers = {
                "accept": "*/*",
                "authorization": self._auth_header,
                "content-type": "application/json",
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            }

            while True:
                # Ждем начала следующей минуты
                now = datetime.now()
                wait_seconds = 60 - now.second
                if wait_seconds <= 0:
                    wait_seconds = 60
                await asyncio.sleep(wait_seconds)
                
                # Добавляем случайную задержку 3-6 секунд
                await asyncio.sleep(uniform(3, 6))
            
                # Проверяем текущий пул
                user_pool = await self.make_request(
                    "GET",
                    f"{self._base_url}/pools/user-pool",
                    headers=headers
                )
                
                if not user_pool or all(user_pool.get(k) is None for k in ('id', 'title')):
                    # Получаем список доступных пулов
                    pools = await self.make_request(
                        "GET",
                        f"{self._base_url}/pools",
                        headers=headers
                    )
                    
                    if pools:
                        # Сортируем пулы по критериям
                        best_pool = None
                        max_score = -1
                        
                        for pool in pools:
                            members = pool.get('numberOfMembers', 0)
                            tokens = pool.get('tokensMined', 0)
                            fee = pool.get('feePercentage', 100)
                            
                            if members >= 40:  # Пропускаем заполненные пулы
                                continue
                                
                            # Считаем score: больше токенов лучше, меньше комиссия лучше
                            score = tokens * (100 - fee)
                            
                            if score > max_score:
                                max_score = score
                                best_pool = pool
                        
                        if best_pool:
                            # Присоединяемся к лучшему пулу
                            join_result = await self.make_request(
                                "POST",
                                f"{self._base_url}/pools/join-invoice",
                                headers=headers,
                                json={
                                    "miningPoolId": str(best_pool['id']),
                                    "poolName": best_pool['title']
                                }
                            )
                            if join_result:
                                logger.info(
                                    f"⭐ {self.session_name} | "
                                    f"Joined pool {best_pool['title']} "
                                    f"(Fee: {best_pool['feePercentage']}%, "
                                    f"Miners: {best_pool['numberOfMembers']}, "
                                    f"Mined: {best_pool['tokensMined']})"
                                )
            
                # Получаем статистику пользователя
                stats = await self.make_request(
                    "GET", 
                    f"{self._base_url}/users/stats",
                    headers=headers
                )
                if stats:
                    tokens_mined = stats.get('tokensMined', 0)
                    ref_count = stats.get('numberOfReferrals', 0)
                    luck_factor = stats.get('luckFactor', 1)
                    has_joined_x = stats.get('hasJoinedX', False)
                    has_joined_community = stats.get('hasJoinedCommunity', False)
                    
                    # Если не подписаны на X, подтверждаем подписку
                    if not has_joined_x:
                        check_x = await self.make_request(
                            "GET",
                            f"{self._base_url}/users/check-x",
                            headers=headers
                        )
                        if check_x and check_x.get('hasJoinedX'):
                            logger.info(f"🎯 {self.session_name} | Twitter subscription confirmed")
                    
                    # Если включена подписка на каналы и не подписаны на сообщество
                    if settings.SUBSCRIBE_TELEGRAM and not has_joined_community:
                        # Подписываемся на канал
                        await self.tg_client.join_telegram_channel({
                            "additional_data": {
                                "username": settings.COMMUNITY_CHANNEL
                            }
                        })
                        await asyncio.sleep(2)
                        
                        # Проверяем подписку
                        check_community = await self.make_request(
                            "GET",
                            f"{self._base_url}/users/check-community",
                            headers=headers
                        )
                        if check_community and check_community.get('hasJoinedCommunity'):
                            logger.info(f"📢 {self.session_name} | Community subscription confirmed")
                    
                    logger.info(
                        f"⛏️ {self.session_name} | "
                        f"Mined: {tokens_mined:.6f} OPEN | "
                        f"Luck: {luck_factor} | "
                        f"Refs: {ref_count} 👥"
                    )

                # Получаем информацию о последнем блоке
                latest_block = await self.make_request(
                    "GET",
                    f"{self._base_url}/blocks/latest",
                    headers=headers
                )
                if not latest_block:
                    continue

                self._current_block_id = latest_block.get("id")
                if not self._current_block_id:
                    continue

                if not self._after_block_id:
                    self._after_block_id = self._current_block_id - 1

                # Если не майним, начинаем майнинг
                if not latest_block.get("isUserMining", False):
                    result = await self.make_request(
                        "POST",
                        f"{self._base_url}/blocks/start-mining",
                        headers=headers,
                        json={"blockId": self._current_block_id}
                    )
                    if result is not None:
                        miners_count = latest_block.get('minersCount', 0)
                        logger.info(
                            f"🚀 {self.session_name} | "
                            f"Started mining block {self._current_block_id} "
                            f"with {miners_count} miners"
                        )

                # Проверяем результаты
                results = await self.make_request(
                    "GET",
                    f"{self._base_url}/blocks/user-results?afterBlockId={self._after_block_id}&currentBlockId={self._current_block_id}",
                    headers=headers
                ) or []
                
                for result in results:
                    if isinstance(result, dict):
                        rewards = result.get('rewards', 0)
                        block_id = result.get('block_id')
                        if block_id:
                            logger.info(
                                f"💎 {self.session_name} | "
                                f"Got {rewards:.6f} OPEN "
                                f"from block {block_id}"
                            )
                            self._after_block_id = max(self._after_block_id, int(block_id))

        except Exception as e:
            logger.error(f"❌ {self.session_name} | Mining error: {str(e)}")


async def run_tapper(tg_client: UniversalTelegramClient):
    """
    Функция для запуска бота.
    
    Args:
        tg_client: Клиент Telegram
    """
    bot = BaseBot(tg_client=tg_client)
    try:
        await bot.run()
    except InvalidSession as e:
        logger.error(f"Invalid Session: {e}")
