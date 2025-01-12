import aiohttp
import asyncio
from typing import Dict, Optional, Any, Tuple, List, Union
from urllib.parse import urlencode, unquote
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from random import uniform, randint, choice
from time import time
from datetime import datetime, timezone, time
import json
import os

from bot.utils.universal_telegram_client import UniversalTelegramClient
from bot.utils.proxy_utils import check_proxy, get_working_proxy
from bot.utils.first_run import check_is_first_run, append_recurring_session
from bot.config import settings
from bot.utils import logger, config_utils, CONFIG_PATH
from bot.exceptions import InvalidSession
from bot.core.headers import get_toc_headers
from bot.core.agents import generate_random_user_agent
from bot.utils.captcha_solver import solve_captcha


class BaseBot:
    
    def __init__(self, tg_client: UniversalTelegramClient):
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
        self._last_auth_time: Optional[float] = None
        self._auth_interval: int = 3600
        self._mined_blocks_count: int = 0
        self._target_blocks: Optional[int] = None
        self._pools_url = "https://gist.githubusercontent.com/Mffff4/ac493d4c9e4fa0a87a70c57e6f251c31/raw"
        self._current_pool_id = None
        
        session_config = config_utils.get_session_config(self.session_name, CONFIG_PATH)
        if not all(key in session_config for key in ('api', 'user_agent')):
            logger.critical(f"CHECK accounts_config.json as it might be corrupted")
            exit(-1)
            
        self.proxy = session_config.get('proxy')
        if self.proxy:
            proxy = Proxy.from_str(self.proxy)
            self.tg_client.set_proxy(proxy)
            self._current_proxy = self.proxy

        self._base_url = "https://miniapp.theopencoin.xyz/api/v1"

    def get_ref_id(self) -> str:
        if self._current_ref_id is None:
            random_number = randint(1, 100)
            self._current_ref_id = settings.REF_ID if random_number <= 70 else 'ref_b2434667eb27d01f'
        return self._current_ref_id

    async def get_tg_web_data(self, app_name: str = "app", path: str = "app") -> str:
        try:
            ref_id = self.get_ref_id()
            webview_url = await self.tg_client.get_webview_url(
                bot_username="@TheOpenCoin_bot",
                bot_url="https://miniapp.theopencoin.xyz/",
                default_val=ref_id
            )
            
            if not webview_url:
                logger.error(f"❌ {self.session_name} | Failed to get webview URL: URL is None")
                raise InvalidSession("Failed to get webview URL")
            
            try:
                tg_web_data = webview_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]
                tg_web_data = unquote(string=tg_web_data)
                self._init_data = tg_web_data
                return tg_web_data
                
            except (IndexError, AttributeError) as e:
                logger.error(f"❌ {self.session_name} | Failed to parse webview URL: {str(e)}")
                raise InvalidSession("Failed to parse webview URL")
            
        except Exception as e:
            logger.error(f"❌ {self.session_name} | Error getting TG Web Data: {str(e)}")
            if isinstance(e, InvalidSession):
                raise
            raise InvalidSession("Failed to get TG Web Data")

    async def check_and_update_proxy(self, accounts_config: dict) -> bool:
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
        if not self._http_client:
            raise InvalidSession("HTTP client not initialized")

        max_retries = 3
        retry_delay = 1
        last_error = None
        
        for attempt in range(max_retries):
            try:
                async with getattr(self._http_client, method.lower())(url, **kwargs) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 409:
                        response_json = await response.json()
                        if isinstance(response_json, dict) and response_json.get('code') == 'capture_required':
                            return response_json
                        logger.error(f"Request conflict (409): {await response.text()}")
                        return None
                    elif response.status == 500:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                        return None
                    else:
                        logger.error(f"Request failed with status {response.status}")
                        return None
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                
        if last_error:
            logger.error(f"Request error after {max_retries} retries: {str(last_error)}")
        return None

    async def run(self) -> None:
        if not await self.initialize_session():
            return

        delay = uniform(1, settings.SESSION_START_DELAY)
        logger.info(f"{self.session_name} | Starting in {int(delay)} seconds")
        await asyncio.sleep(delay)
            
        while True:
            try:
                if settings.NIGHT_MODE:
                    current_utc_time = datetime.now(timezone.utc).time()
                    logger.info(f"{self.session_name} | Checking night mode: Current UTC time is {current_utc_time.replace(microsecond=0)}")

                    start_time = time(hour=settings.NIGHT_TIME[0], minute=settings.NIGHT_TIME[1])
                    end_time = time(hour=7)

                    next_checking_time = randint(settings.NIGHT_CHECKING[0], settings.NIGHT_CHECKING[1])

                    current_minutes = current_utc_time.hour * 60 + current_utc_time.minute
                    start_minutes = start_time.hour * 60 + start_time.minute
                    end_minutes = end_time.hour * 60 + end_time.minute

                    is_sleep_time = False
                    if start_minutes <= end_minutes:
                        is_sleep_time = start_minutes <= current_minutes <= end_minutes
                    else:
                        is_sleep_time = current_minutes >= start_minutes or current_minutes <= end_minutes

                    if is_sleep_time:
                        logger.info(
                            f"{self.session_name} | 😴 Night-Mode activated (sleep period: {start_time} - {end_time} UTC)"
                            f"\n💤 Current UTC time: {current_utc_time.replace(microsecond=0)}"
                            f"\n⏰ Next check in {round(next_checking_time / 3600, 1)} hours"
                        )
                        await asyncio.sleep(next_checking_time)
                        continue
                    else:
                        logger.info(f"{self.session_name} | Night-Mode is off until {start_time} UTC")

                proxy_conn = {'connector': ProxyConnector.from_url(self._current_proxy)} if self._current_proxy else {}
                async with CloudflareScraper(timeout=aiohttp.ClientTimeout(60), **proxy_conn) as http_client:
                    self._http_client = http_client

                    session_config = config_utils.get_session_config(self.session_name, CONFIG_PATH)
                    if not await self.check_and_update_proxy(session_config):
                        logger.warning('Failed to find working proxy. Sleep 5 minutes.')
                        await asyncio.sleep(300)
                        continue

                    await self.process_bot_logic()
                    
            except InvalidSession as e:
                raise
            except Exception as error:
                sleep_duration = uniform(60, 120)
                logger.error(f"Unknown error: {error}. Sleeping for {int(sleep_duration)}")
                await asyncio.sleep(sleep_duration)

    async def vote_for_proposal(self, headers: Dict[str, str]) -> None:
        try:
            proposals = await self.make_request(
                "GET",
                f"{self._base_url}/proposals",
                headers=headers
            )
            
            if not proposals:
                return
                
            active_proposals = [p for p in proposals if p.get("status") == "pending"]
            
            if not active_proposals:
                return
                
            for proposal in active_proposals:
                proposal_id = proposal.get("id")
                if not proposal_id:
                    continue
                    
                votes = await self.make_request(
                    "GET",
                    f"{self._base_url}/proposals/{proposal_id}/votes",
                    headers=headers
                )
                
                if not votes or votes.get("userVote"):
                    continue
                    
                recent_votes = votes.get("recentVotes", [])
                vote_options = [vote.get("votesForProposal", True) for vote in recent_votes]
                
                if not vote_options:
                    vote_for = True
                else:
                    vote_for = choice(vote_options)
                    
                vote_result = await self.make_request(
                    "POST",
                    f"{self._base_url}/proposals/{proposal_id}/vote",
                    headers=headers,
                    json={
                        "voteForProposal": vote_for,
                        "proposalId": proposal_id
                    }
                )
                
                if vote_result:
                    logger.info(
                        f"🗳️ {self.session_name} | "
                        f"Voted {'FOR' if vote_for else 'AGAINST'} "
                        f"proposal #{proposal_id}: {proposal.get('title')}"
                    )
        except Exception as e:
            logger.error(f"❌ {self.session_name} | Voting error: {str(e)}")

    async def check_vote_status(self, headers: Dict[str, str]) -> None:
        try:
            stats = await self.make_request(
                "GET",
                f"{self._base_url}/users/stats",
                headers=headers
            )
            
            if not stats or stats.get('hasVoted', True):
                return
                
            check_vote = await self.make_request(
                "GET",
                f"{self._base_url}/users/check-voted",
                headers=headers
            )
            
            if check_vote and check_vote.get('hasVoted'):
                logger.info(f"🗳️ {self.session_name} | Vote status confirmed")
        except Exception as e:
            logger.error(f"❌ {self.session_name} | Vote status check error: {str(e)}")
   
    async def check_and_join_telegram_chat(self, headers: Dict[str, str]) -> bool:
        try:
            chat_status = await self.make_request(
                "GET",
                f"{self._base_url}/users/check-chat",
                headers=headers
            )
            
            if not chat_status or chat_status.get("hasJoinedChat"):
                return True
                
            chat_username = "theopencoin_chat"
            try:
                await self.tg_client.join_chat(chat_username)
                logger.info(f"{self.session_name} | Successfully joined chat @{chat_username}")
                
                await asyncio.sleep(2)
                verify_status = await self.make_request(
                    "GET",
                    f"{self._base_url}/users/check-chat",
                    headers=headers
                )
                
                return verify_status and verify_status.get("hasJoinedChat", False)
                
            except Exception as e:
                logger.error(f"{self.session_name} | Error joining chat: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"{self.session_name} | Error checking chat status: {str(e)}")
            return False

    async def _try_join_pool(self, headers: Dict[str, str]) -> bool:
        try:
            if not settings.JOIN_POOL:
                return False

            user_pool = await self.make_request(
                "GET",
                f"{self._base_url}/pools/user-pool",
                headers=headers
            )

            if user_pool and user_pool.get('id') is not None:
                self._current_pool_id = user_pool.get('id')
                logger.info(f"✅ {self.session_name} | Already in pool: {user_pool.get('title')}")
                return True

            async with aiohttp.ClientSession() as session:
                async with session.get(self._pools_url) as response:
                    if response.status != 200:
                        logger.error(f"❌ {self.session_name} | Failed to fetch pools list")
                        return False
                    try:
                        response_text = await response.text()
                        pools_data = json.loads(response_text)
                    except Exception as e:
                        logger.error(f"❌ {self.session_name} | Failed to parse pools data")
                        return False

            if not pools_data or 'pools' not in pools_data:
                logger.error(f"❌ {self.session_name} | Invalid pools data format")
                return False

            for pool_url in pools_data['pools']:
                try:
                    pool_id = pool_url.split('pool_')[1]

                    if not await self.tg_client.send_start_command(pool_id):
                        continue

                    await asyncio.sleep(2)

                    user_pool = await self.make_request(
                        "GET",
                        f"{self._base_url}/pools/user-pool",
                        headers=headers
                    )

                    if user_pool and user_pool.get('id') is not None:
                        self._current_pool_id = user_pool.get('id')
                        logger.info(f"✅ {self.session_name} | Successfully joined pool {user_pool.get('title')}")
                        return True

                except Exception as e:
                    continue

            logger.warning(f"⚠️ {self.session_name} | Failed to join any pool, will retry in next cycle")
            return False

        except Exception as e:
            logger.error(f"❌ {self.session_name} | Pool joining error: {str(e)}")
            return False

    async def process_bot_logic(self) -> None:
        try:
            if not hasattr(self, '_auth_header'):
                self._auth_header = None
                self._current_block_id = None
                self._after_block_id = None
                self._last_auth_time = None
            
            current_time = time()
            
            if not self._auth_header or not self._last_auth_time or (current_time - self._last_auth_time) >= self._auth_interval:
                tg_web_data = await self.get_tg_web_data()
                self._auth_header = tg_web_data
                self._last_auth_time = current_time
            
            headers = get_toc_headers(self._auth_header)
            
            await self.check_and_join_telegram_chat(headers)
            
            await self.vote_for_proposal(headers)
            await self.check_vote_status(headers)
            
            await self._try_join_pool(headers)

            while True:
                if not self._target_blocks and settings.BLOCKS_BEFORE_SLEEP != (0, 0):
                    self._target_blocks = randint(
                        settings.BLOCKS_BEFORE_SLEEP[0],
                        settings.BLOCKS_BEFORE_SLEEP[1]
                    )
                    logger.info(
                        f"🎲 {self.session_name} | "
                        f"Target set: {self._target_blocks} blocks before sleep"
                    )

                if (settings.BLOCKS_BEFORE_SLEEP != (0, 0) and 
                    self._target_blocks and 
                    self._mined_blocks_count >= self._target_blocks):
                    sleep_hours = uniform(settings.SLEEP_HOURS[0], settings.SLEEP_HOURS[1])
                    sleep_seconds = int(sleep_hours * 3600)
                    logger.info(
                        f"😴 {self.session_name} | "
                        f"Mined {self._mined_blocks_count} blocks. "
                        f"Going to sleep for {sleep_hours:.1f} hours"
                    )
                    await asyncio.sleep(sleep_seconds)
                    self._mined_blocks_count = 0
                    self._target_blocks = None
                    self._auth_header = None
                    self._last_auth_time = None
                    logger.info(f"🌅 {self.session_name} | Woke up! Restarting mining cycle")
                    break

                now = datetime.now()
                wait_seconds = 60 - now.second
                if wait_seconds <= 0:
                    wait_seconds = 60
                await asyncio.sleep(wait_seconds)
                
                await asyncio.sleep(uniform(3, 38))
            
                user_pool = await self.make_request(
                    "GET",
                    f"{self._base_url}/pools/user-pool",
                    headers=headers
                )
                
                if user_pool and user_pool.get('id') is not None:
                    pool_info = (
                        f"Pool: {user_pool.get('title')} | "
                        f"Fee: {user_pool.get('fee_percentage')}% | "
                        f"Miners: {user_pool.get('number_of_miners')} | "
                        f"Mined: {user_pool.get('tokens_mined', 0)}"
                    )
                    logger.info(f"⛏️ {self.session_name} | {pool_info}")
                else:
                    logger.info(f"⛏️ {self.session_name} | Not in pool")

                stats = await self.make_request(
                    "GET", 
                    f"{self._base_url}/users/stats",
                    headers=headers
                )
                if stats:
                    tokens_mined = stats.get('tokensMined', 0) or 0
                    ref_count = stats.get('numberOfReferrals', 0) or 0
                    luck_factor = stats.get('luckFactor', 1) or 1
                    has_joined_x = stats.get('hasJoinedX', False)
                    has_joined_community = stats.get('hasJoinedCommunity', False)
                    
                    if not has_joined_x:
                        check_x = await self.make_request(
                            "GET",
                            f"{self._base_url}/users/check-x",
                            headers=headers
                        )
                        if check_x and check_x.get('hasJoinedX'):
                            logger.info(f"🎯 {self.session_name} | Twitter subscription confirmed")
                    
                    if settings.SUBSCRIBE_TELEGRAM and not has_joined_community:
                        await self.tg_client.join_telegram_channel({
                            "additional_data": {
                                "username": settings.COMMUNITY_CHANNEL
                            }
                        })
                        await asyncio.sleep(2)
                        
                        check_community = await self.make_request(
                            "GET",
                            f"{self._base_url}/users/check-community",
                            headers=headers
                        )
                        if check_community and check_community.get('hasJoinedCommunity'):
                            logger.info(f"📢 {self.session_name} | Community subscription confirmed")
                    
                    logger.info(
                        f"⛏️ {self.session_name} | "
                        f"Mined: {float(tokens_mined):.6f} OPEN | "
                        f"Luck: {float(luck_factor)} | "
                        f"Refs: {int(ref_count)} 👥"
                    )

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

                if not latest_block.get("isUserMining", False):
                    result = await self.make_request(
                        "POST",
                        f"{self._base_url}/blocks/start-mining",
                        headers=headers,
                        json={"blockId": self._current_block_id}
                    )
                    
                    if isinstance(result, dict):
                        if result.get('code') == 'capture_required':
                            capture_data = result.get('capture')
                            if capture_data:
                                if await self.verify_capture(headers, capture_data):
                                    result = await self.make_request(
                                        "POST",
                                        f"{self._base_url}/blocks/start-mining",
                                        headers=headers,
                                        json={"blockId": self._current_block_id}
                                    )
                                else:
                                    logger.error(f"❌ {self.session_name} | Failed to pass the captcha")
                                    exit(1)
                        elif result.get('code') == 'user_blocked':
                            block_minutes = int(result.get('message', '').split()[6])
                            logger.warning(
                                f"⛔️ {self.session_name} | User is blocked from mining for {block_minutes} minutes"
                                f"\n💤 Going to sleep..."
                            )
                            await asyncio.sleep(block_minutes * 60)
                            self._auth_header = None
                            self._last_auth_time = None
                            break
                    
                    if result is not None:
                        miners_count = latest_block.get('minersCount', 0)
                        logger.info(
                            f"🚀 {self.session_name} | "
                            f"Started mining block {self._current_block_id} "
                            f"with {miners_count} miners"
                        )

                results = await self.make_request(
                    "GET",
                    f"{self._base_url}/blocks/user-results?afterBlockId={self._after_block_id}&currentBlockId={self._current_block_id}",
                    headers=headers
                ) or []
                
                for result in results:
                    if isinstance(result, dict):
                        rewards = result.get('rewards', 0) or 0
                        block_id = result.get('block_id')
                        if block_id:
                            self._mined_blocks_count += 1
                            logger.info(
                                f"💎 {self.session_name} | "
                                f"Got {float(rewards):.6f} OPEN "
                                f"from block {block_id} "
                                f"[{self._mined_blocks_count}/{self._target_blocks if self._target_blocks else '∞'}]"
                            )
                            if rewards and float(rewards) >= 10:
                                logger.info(f"🎯 {self.session_name} | 🎉 BIG WIN! {float(rewards):.6f} TOC")
                            
                            self._after_block_id = max(self._after_block_id, int(block_id))

        except Exception as e:
            logger.error(f"❌ {self.session_name} | Mining error: {str(e)}")

    async def verify_capture(self, headers: Dict[str, str], capture_data: Union[Dict[str, Any], str]) -> bool:
        try:
            if isinstance(capture_data, str):
                solution = await solve_captcha(capture_data)
                if solution:
                    verify_response = await self.make_request(
                        "POST",
                        f"{self._base_url}/captures/verify",
                        headers=headers,
                        json={
                            "captureType": solution.type,
                            "captureContext": {"c": solution.answer} if solution.type != "STARS_V1" else {"a": solution.answer}
                        }
                    )
                    return verify_response is not None
                else:
                    logger.error(f"❌ {self.session_name} | Failed to solve encrypted captcha")
                    return False
            
            if not isinstance(capture_data, dict):
                logger.error(f"❌ {self.session_name} | Invalid capture_data type: {type(capture_data)}")
                return False
                
            capture_type = capture_data.get('type')
            context = capture_data.get('context')
            
            if capture_type == 'SUMM_V1':
                if isinstance(context, str):
                    solution = await solve_captcha(context)
                    if solution:
                        verify_response = await self.make_request(
                            "POST",
                            f"{self._base_url}/captures/verify",
                            headers=headers,
                            json={
                                "captureType": capture_type,
                                "captureContext": {"c": solution.answer}
                            }
                        )
                        return verify_response is not None
                    else:
                        logger.error(f"❌ {self.session_name} | Failed to solve captcha")
                        return False
                else:
                    a = context.get('a', 0)
                    b = context.get('b', 0)
                    result = a + b
                    verify_response = await self.make_request(
                        "POST",
                        f"{self._base_url}/captures/verify",
                        headers=headers,
                        json={
                            "captureType": capture_type,
                            "captureContext": {"c": result}
                        }
                    )
                    return verify_response is not None
            elif capture_type == 'STARS_V1':
                if isinstance(context, str):
                    solution = await solve_captcha(context)
                    if solution:
                        verify_response = await self.make_request(
                            "POST",
                            f"{self._base_url}/captures/verify",
                            headers=headers,
                            json={
                                "captureType": capture_type,
                                "captureContext": {"a": solution.answer}
                            }
                        )
                        return verify_response is not None
                    else:
                        logger.error(f"❌ {self.session_name} | Failed to solve captcha")
                        return False
                else:
                    a = context.get('a', 0)
                    verify_response = await self.make_request(
                        "POST",
                        f"{self._base_url}/captures/verify",
                        headers=headers,
                        json={
                            "captureType": capture_type,
                            "captureContext": {"a": a}
                        }
                    )
                    return verify_response is not None
            elif capture_type == 'MULTIPLY_V1':
                if isinstance(context, str):
                    solution = await solve_captcha(context)
                    if solution:
                        verify_response = await self.make_request(
                            "POST",
                            f"{self._base_url}/captures/verify",
                            headers=headers,
                            json={
                                "captureType": capture_type,
                                "captureContext": {"c": solution.answer}
                            }
                        )
                        return verify_response is not None
                    else:
                        logger.error(f"❌ {self.session_name} | Failed to solve captcha")
                        return False
                else:
                    a = context.get('a', 0)
                    b = context.get('b', 0)
                    result = a * b
                    verify_response = await self.make_request(
                        "POST",
                        f"{self._base_url}/captures/verify",
                        headers=headers,
                        json={
                            "captureType": capture_type,
                            "captureContext": {"c": result}
                        }
                    )
                    return verify_response is not None
            elif capture_type == 'SUBTRACT_V1':
                if isinstance(context, str):
                    solution = await solve_captcha(context)
                    if solution:
                        verify_response = await self.make_request(
                            "POST",
                            f"{self._base_url}/captures/verify",
                            headers=headers,
                            json={
                                "captureType": capture_type,
                                "captureContext": {"c": solution.answer}
                            }
                        )
                        return verify_response is not None
                    else:
                        logger.error(f"❌ {self.session_name} | Failed to solve captcha")
                        return False
                else:
                    a = context.get('a', 0)
                    b = context.get('b', 0)
                    result = a - b
                    verify_response = await self.make_request(
                        "POST",
                        f"{self._base_url}/captures/verify",
                        headers=headers,
                        json={
                            "captureType": capture_type,
                            "captureContext": {"c": result}
                        }
                    )
                    return verify_response is not None
            else:
                logger.error(
                    f"❌ {self.session_name} | "
                    f"New captcha type: {capture_type}. "
                    f"Context: {context}"
                )
                logger.error("Please report this at t.me/mffff4")
                return False
                
        except Exception as e:
            logger.error(f"❌ {self.session_name} | Captcha verification error: {str(e)}")
            return False


async def run_tapper(tg_client: UniversalTelegramClient):
    bot = BaseBot(tg_client=tg_client)
    try:
        await bot.run()
    except InvalidSession as e:
        logger.error(f"Invalid Session: {e}")
