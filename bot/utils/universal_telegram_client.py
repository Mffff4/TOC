import asyncio
import os
from better_proxy import Proxy
from datetime import datetime, timedelta
from random import randint, uniform
from sqlite3 import OperationalError
from typing import Union

from opentele.tl import TelegramClient
from telethon.errors import *
from telethon.functions import messages, channels, account, folders
from telethon.network import ConnectionTcpAbridged
from telethon.types import InputBotAppShortName, InputPeerNotifySettings, InputNotifyPeer, InputUser
from telethon import types as raw

import pyrogram.raw.functions.account as paccount
import pyrogram.raw.functions.channels as pchannels
import pyrogram.raw.functions.messages as pmessages
import pyrogram.raw.functions.folders as pfolders
from pyrogram import Client as PyrogramClient
from pyrogram.errors import *
from pyrogram.raw import types as ptypes

from bot.config import settings
from bot.exceptions import InvalidSession
from bot.utils.proxy_utils import to_pyrogram_proxy, to_telethon_proxy
from bot.utils import logger, log_error, AsyncInterProcessLock, CONFIG_PATH, first_run


class UniversalTelegramClient:
    def __init__(self, **client_params):
        self.session_name = None
        self.client: Union[TelegramClient, PyrogramClient]
        self.proxy = None
        self.is_first_run = True
        self.is_pyrogram: bool = False
        self._client_params = client_params
        self._init_client()
        self.default_val = 'ref_b2434667eb27d01f'
        self.lock = AsyncInterProcessLock(
            os.path.join(os.path.dirname(CONFIG_PATH), 'lock_files', f"{self.session_name}.lock"))
        self._webview_data = None
        self.ref_id = None  # Будет установлен позже

    def _init_client(self):
        try:
            self.client = TelegramClient(connection=ConnectionTcpAbridged, **self._client_params)
            self.client.parse_mode = None
            self.client.no_updates = True
            self.is_pyrogram = False
            self.session_name, _ = os.path.splitext(os.path.basename(self.client.session.filename))
        except OperationalError:
            session_name = self._client_params.pop('session')
            self._client_params.pop('system_lang_code')
            self._client_params['name'] = session_name
            self.client = PyrogramClient(**self._client_params)
            self.client.no_updates = True
            self.client.run = lambda *args, **kwargs: None
            self.is_pyrogram = True
            self.session_name, _ = os.path.splitext(os.path.basename(self.client.name))

    def set_proxy(self, proxy: Proxy):
        if not self.is_pyrogram:
            self.proxy = to_telethon_proxy(proxy)
            self.client.set_proxy(self.proxy)
        else:
            self.proxy = to_pyrogram_proxy(proxy)
            self.client.proxy = self.proxy

    async def get_app_webview_url(self, bot_username: str, bot_shortname: str, default_val: str) -> str:
        self.is_first_run = await first_run.check_is_first_run(self.session_name)
        return await self._pyrogram_get_app_webview_url(bot_username, bot_shortname, default_val) if self.is_pyrogram \
            else await self._telethon_get_app_webview_url(bot_username, bot_shortname, default_val)

    async def get_webview_url(self, bot_username: str, bot_url: str, default_val: str) -> str:
        self.is_first_run = await first_run.check_is_first_run(self.session_name)
        return await self._pyrogram_get_webview_url(bot_username, bot_url, default_val) if self.is_pyrogram \
            else await self._telethon_get_webview_url(bot_username, bot_url, default_val)

    async def join_and_mute_tg_channel(self, link: str):
        return await self._pyrogram_join_and_mute_tg_channel(link) if self.is_pyrogram \
            else await self._telethon_join_and_mute_tg_channel(link)

    async def update_profile(self, first_name: str = None, last_name: str = None, about: str = None):
        return await self._pyrogram_update_profile(first_name=first_name, last_name=last_name, about=about) if self.is_pyrogram \
            else await self._telethon_update_profile(first_name=first_name, last_name=last_name, about=about)

    async def _telethon_initialize_webview_data(self, bot_username: str, bot_shortname: str = None):
        if not self._webview_data:
            while True:
                try:
                    peer = await self.client.get_input_entity(bot_username)
                    bot_id = InputUser(user_id=peer.user_id, access_hash=peer.access_hash)
                    input_bot_app = InputBotAppShortName(bot_id=bot_id, short_name=bot_shortname)
                    self._webview_data = {'peer': peer, 'app': input_bot_app} if bot_shortname \
                        else {'peer': peer, 'bot': peer}
                    return
                except FloodWaitError as fl:
                    logger.warning(f"<ly>{self.session_name}</ly> | FloodWait {fl}. Waiting {fl.seconds}s")
                    await asyncio.sleep(fl.seconds + 3)

    async def _telethon_get_app_webview_url(self, bot_username: str, bot_shortname: str, default_val: str) -> str:
        if self.proxy and not self.client._proxy:
            logger.critical(f"<ly>{self.session_name}</ly> | Proxy found, but not passed to TelegramClient")
            exit(-1)

        async with self.lock:
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                await self._telethon_initialize_webview_data(bot_username=bot_username, bot_shortname=bot_shortname)
                await asyncio.sleep(uniform(1, 2))

                ref_id = default_val
                start = {'start_param': ref_id}

                web_view = await self.client(messages.RequestAppWebViewRequest(
                    **self._webview_data,
                    platform='android',
                    write_allowed=True,
                    **start
                ))

                url = web_view.url
                
                if 'tgWebAppStartParam=' not in url:
                    separator = '?' if '#' in url else '&#'
                    insert_pos = url.find('#') if '#' in url else len(url)
                    url = f"{url[:insert_pos]}{separator}tgWebAppStartParam={ref_id}{url[insert_pos:]}"

                return url

            except (UnauthorizedError, AuthKeyUnregisteredError):
                raise InvalidSession(f"{self.session_name}: User is unauthorized")
            except (UserDeactivatedError, UserDeactivatedBanError, PhoneNumberBannedError):
                raise InvalidSession(f"{self.session_name}: User is banned")

            except Exception:
                raise

            finally:
                if self.client.is_connected():
                    await self.client.disconnect()
                    await asyncio.sleep(15)

    async def _telethon_get_webview_url(self, bot_username: str, bot_url: str, default_val: str) -> str:
        if self.proxy and not self.client._proxy:
            logger.critical(f"<ly>{self.session_name}</ly> | Proxy found, but not passed to TelegramClient")
            exit(-1)

        async with self.lock:
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                await self._telethon_initialize_webview_data(bot_username=bot_username)
                await asyncio.sleep(uniform(1, 2))

                ref_id = self.get_ref_id()
                start = {'start_param': ref_id} if self.is_first_run else {}

                start_state = False
                async for message in self.client.iter_messages(bot_username):
                    if r'/start' in message.text:
                        start_state = True
                        break
                await asyncio.sleep(uniform(0.5, 1))
                if not start_state:
                    await self.client(messages.StartBotRequest(
                        **self._webview_data,
                        start_param=ref_id,
                        random_id=randint(1, 2**63)
                    ))
                await asyncio.sleep(uniform(1, 2))

                web_view = await self.client(messages.RequestWebViewRequest(
                    **self._webview_data,
                    platform='android',
                    from_bot_menu=False,
                    url=bot_url,
                    **start
                ))

                return web_view.url

            except (UnauthorizedError, AuthKeyUnregisteredError):
                raise InvalidSession(f"{self.session_name}: User is unauthorized")
            except (UserDeactivatedError, UserDeactivatedBanError, PhoneNumberBannedError):
                raise InvalidSession(f"{self.session_name}: User is banned")

            except Exception:
                raise

            finally:
                if self.client.is_connected():
                    await self.client.disconnect()
                    await asyncio.sleep(15)

    async def _pyrogram_initialize_webview_data(self, bot_username: str, bot_shortname: str = None):
        if not self._webview_data:
            while True:
                try:
                    peer = await self.client.resolve_peer(bot_username)
                    if not peer:
                        raise Exception("Failed to resolve peer")
                        
                    input_bot_app = ptypes.InputBotAppShortName(bot_id=peer, short_name=bot_shortname)
                    self._webview_data = {'peer': peer, 'app': input_bot_app} if bot_shortname \
                        else {'peer': peer, 'bot': peer}
                    return
                    
                except FloodWait as fl:
                    logger.warning(f"<ly>{self.session_name}</ly> | FloodWait {fl}. Waiting {fl.value}s")
                    await asyncio.sleep(fl.value + 3)
                except Exception as e:
                    logger.error(f"❌ {self.session_name} | Error initializing web view data: {str(e)}")
                    raise

    async def _pyrogram_get_app_webview_url(self, bot_username: str, bot_shortname: str, default_val: str) -> str:
        if self.proxy and not self.client.proxy:
            logger.critical(f"<ly>{self.session_name}</ly> | Proxy found, but not passed to Client")
            exit(-1)

        async with self.lock:
            try:
                if not self.client.is_connected:
                    await self.client.connect()
                
                await self._pyrogram_initialize_webview_data(bot_username)
                await asyncio.sleep(uniform(1, 2))
                
                start_param = default_val
                start = {'start_param': start_param}

                start_state = False
                try:
                    async for message in self.client.get_chat_history(bot_username):
                        if message and message.text and r'/start' in message.text:
                            start_state = True
                            break
                except Exception as e:
                    start_state = False
                
                await asyncio.sleep(uniform(0.5, 1))
                
                if not start_state:
                    try:
                        await self.client.invoke(pmessages.StartBot(
                            **self._webview_data,
                            random_id=randint(1, 2**63),
                            start_param=start_param
                        ))
                    except Exception as e:
                        logger.error(f"❌ {self.session_name} | Failed to send start command: {str(e)}")
                        raise
                
                await asyncio.sleep(uniform(1, 2))
                
                web_view = await self.client.invoke(pmessages.RequestWebView(
                    **self._webview_data,
                    platform='android',
                    from_bot_menu=False,
                    url=bot_shortname,
                    **start
                ))
                
                if not web_view:
                    logger.error(f"❌ {self.session_name} | Web view request returned None")
                    return None
                
                return web_view.url

            except (Unauthorized, AuthKeyUnregistered):
                logger.error(f"❌ {self.session_name} | User is unauthorized")
                raise InvalidSession(f"{self.session_name}: User is unauthorized")
            except (UserDeactivated, UserDeactivatedBan, PhoneNumberBanned):
                logger.error(f"❌ {self.session_name} | User is banned")
                raise InvalidSession(f"{self.session_name}: User is banned")
            except Exception as e:
                logger.error(f"❌ {self.session_name} | Error in get_webview_url: {str(e)}")
                raise

            finally:
                if self.client.is_connected:
                    await self.client.disconnect()
                    await asyncio.sleep(15)

    async def _pyrogram_get_webview_url(self, bot_username: str, bot_url: str, default_val: str) -> str:
        if self.proxy and not self.client.proxy:
            logger.critical(f"<ly>{self.session_name}</ly> | Proxy found, but not passed to Client")
            exit(-1)

        async with self.lock:
            try:
                if not self.client.is_connected:
                    await self.client.connect()
                
                await self._pyrogram_initialize_webview_data(bot_username)
                await asyncio.sleep(uniform(1, 2))
                
                start_param = default_val
                start = {'start_param': start_param}

                start_state = False
                try:
                    async for message in self.client.get_chat_history(bot_username):
                        if message and message.text and r'/start' in message.text:
                            start_state = True
                            break
                except Exception as e:
                    start_state = False
                
                await asyncio.sleep(uniform(0.5, 1))
                
                if not start_state:
                    try:
                        await self.client.invoke(pmessages.StartBot(
                            **self._webview_data,
                            random_id=randint(1, 2**63),
                            start_param=start_param
                        ))
                    except Exception as e:
                        logger.error(f"❌ {self.session_name} | Failed to send start command: {str(e)}")
                        raise
                
                await asyncio.sleep(uniform(1, 2))
                
                web_view = await self.client.invoke(pmessages.RequestWebView(
                    **self._webview_data,
                    platform='android',
                    from_bot_menu=False,
                    url=bot_url,
                    **start
                ))
                
                if not web_view:
                    logger.error(f"❌ {self.session_name} | Web view request returned None")
                    return None
                
                return web_view.url

            except (Unauthorized, AuthKeyUnregistered):
                logger.error(f"❌ {self.session_name} | User is unauthorized")
                raise InvalidSession(f"{self.session_name}: User is unauthorized")
            except (UserDeactivated, UserDeactivatedBan, PhoneNumberBanned):
                logger.error(f"❌ {self.session_name} | User is banned")
                raise InvalidSession(f"{self.session_name}: User is banned")
            except Exception as e:
                logger.error(f"❌ {self.session_name} | Error in get_webview_url: {str(e)}")
                raise

            finally:
                if self.client.is_connected:
                    await self.client.disconnect()
                    await asyncio.sleep(15)

    async def _telethon_join_and_mute_tg_channel(self, link: str):
        path = link.replace("https://t.me/", "")
        if path == 'money':
            return

        async with self.lock:
            async with self.client as client:
                try:
                    if path.startswith('+'):
                        invite_hash = path[1:]
                        result = await client(messages.ImportChatInviteRequest(hash=invite_hash))
                        channel_title = result.chats[0].title
                        entity = result.chats[0]
                    else:
                        entity = await client.get_entity(f'@{path}')
                        await client(channels.JoinChannelRequest(channel=entity))
                        channel_title = entity.title

                    await asyncio.sleep(1)

                    await client(account.UpdateNotifySettingsRequest(
                        peer=InputNotifyPeer(entity),
                        settings=InputPeerNotifySettings(
                            show_previews=False,
                            silent=True,
                            mute_until=datetime.today() + timedelta(days=365)
                        )
                    ))

                    logger.info(f"<ly>{self.session_name}</ly> | Subscribed to channel: <y>{channel_title}</y>")
                except FloodWaitError as fl:
                    logger.warning(f"<ly>{self.session_name}</ly> | FloodWait {fl}. Waiting {fl.seconds}s")
                    return fl.seconds
                except Exception as e:
                    log_error(
                        f"<ly>{self.session_name}</ly> | (Task) Error while subscribing to tg channel {link}: {e}")

            await asyncio.sleep(uniform(15, 20))
        return

    async def _pyrogram_join_and_mute_tg_channel(self, link: str):
        path = link.replace("https://t.me/", "")
        if path == 'money':
            return

        async with self.lock:
            async with self.client:
                try:
                    if path.startswith('+'):
                        invite_hash = path[1:]
                        result = await self.client.invoke(pmessages.ImportChatInvite(hash=invite_hash))
                        channel_title = result.chats[0].title
                        entity = result.chats[0]
                        peer = ptypes.InputPeerChannel(channel_id=entity.id, access_hash=entity.access_hash)
                    else:
                        peer = await self.client.resolve_peer(f'@{path}')
                        channel = ptypes.InputChannel(channel_id=peer.channel_id, access_hash=peer.access_hash)
                        await self.client.invoke(pchannels.JoinChannel(channel=channel))
                        channel_title = path

                    await asyncio.sleep(1)

                    await self.client.invoke(paccount.UpdateNotifySettings(
                        peer=ptypes.InputNotifyPeer(peer=peer),
                        settings=ptypes.InputPeerNotifySettings(
                            show_previews=False,
                            silent=True,
                            mute_until=2147483647))
                    )

                    logger.info(f"<ly>{self.session_name}</ly> | Subscribed to channel: <y>{channel_title}</y>")
                except FloodWait as e:
                    logger.warning(f"<ly>{self.session_name}</ly> | FloodWait {e}. Waiting {e.value}s")
                    return e.value
                except UserAlreadyParticipant:
                    logger.info(f"<ly>{self.session_name}</ly> | Was already Subscribed to channel: <y>{link}</y>")
                except Exception as e:
                    log_error(
                        f"<ly>{self.session_name}</ly> | (Task) Error while subscribing to tg channel {link}: {e}")

            await asyncio.sleep(uniform(15, 20))
        return

    async def _telethon_update_profile(self, first_name: str = None, last_name: str = None, about: str = None):
        update_params = {
            'first_name': first_name,
            'last_name': last_name,
            'about': about
        }
        update_params = {k: v for k, v in update_params.items() if v is not None}
        if not update_params:
            return

        async with self.lock:
            async with self.client:
                try:
                    await self.client(account.UpdateProfileRequest(**update_params))
                except Exception as e:
                    log_error(
                        f"<ly>{self.session_name}</ly> | Failed to update profile: {e}")
            await asyncio.sleep(uniform(15, 20))

    async def _pyrogram_update_profile(self, first_name: str = None, last_name: str = None, about: str = None):
        update_params = {
            'first_name': first_name,
            'last_name': last_name,
            'about': about
        }
        update_params = {k: v for k, v in update_params.items() if v is not None}
        if not update_params:
            return

        async with self.lock:
            async with self.client:
                try:
                    await self.client.invoke(paccount.UpdateProfile(**update_params))
                except Exception as e:
                    log_error(
                        f"<ly>{self.session_name}</ly> | Failed to update profile: {e}")
            await asyncio.sleep(uniform(15, 20))

    def get_ref_id(self) -> str:
        if self.ref_id is None:
            if settings.REF_ID and settings.REF_ID != 'baba':
                self.ref_id = settings.REF_ID
                logger.info(f"{self.session_name} | Using user's referral code: {self.ref_id}")
            else:
                logger.warning(
                    f"\n⚠️ WARNING! Referral code is not specified in the settings!\n"
                    f"All referral rewards will be sent to the developer (ref_b2434667eb27d01f).\n"
                    f"If you want to use your referral code, specify it in the .env file\n"
                    f"To continue with the developer's code, enter 'y', to exit enter any other character:"
                )
                
                user_input = input().strip().lower()
                if user_input != 'y':
                    logger.error("❌ Operation canceled by the user. Please specify your referral code in .env and restart the program.")
                    exit(1)
                    
                logger.info(f"{self.session_name} | Using developer's referral code: ref_b2434667eb27d01f")
                self.ref_id = 'ref_b2434667eb27d01f'
                
        return self.ref_id

    async def join_telegram_channel(self, channel_data: dict) -> bool:
        if not settings.SUBSCRIBE_TELEGRAM:
            logger.info(f"{self.session_name} | Channel subscriptions are disabled in settings")
            return True
            
        channel_username = channel_data.get("additional_data", {}).get("username", "")
        if not channel_username:
            logger.error(f"{self.session_name} | No channel username in task data")
            return False
            
        channel_username = channel_username.replace("@", "")
        
        was_connected = self.client.is_connected if not self.is_pyrogram else self.client.is_connected
        
        try:
            logger.info(f"{self.session_name} | Subscribing to channel <y>{channel_username}</y>")
            
            if not was_connected:
                await self.client.connect()
                
            try:
                if self.is_pyrogram:
                    try:
                        await self.client.join_chat(channel_username)
                        chat = await self.client.get_chat(channel_username)
                        await self._pyrogram_mute_and_archive_channel(chat.id)
                    except UserAlreadyParticipant:
                        logger.info(f"{self.session_name} | Already subscribed to channel <y>{channel_username}</y>")
                    return True
                else:
                    try:
                        await self.client.join_chat(channel_username)
                        chat = await self.client.get_chat(channel_username)
                        await self._telethon_mute_and_archive_channel(chat.id)
                    except UserAlreadyParticipant:
                        logger.info(f"{self.session_name} | Already subscribed to channel <y>{channel_username}</y>")
                    return True
                    
            except FloodWait as e:
                wait_time = e.value if self.is_pyrogram else e.seconds
                logger.warning(f"{self.session_name} | FloodWait for {wait_time} seconds")
                await asyncio.sleep(wait_time)
                return await self.join_telegram_channel(channel_data)
                
            except (UserBannedInChannel, UsernameNotOccupied, UsernameInvalid) as e:
                logger.error(f"{self.session_name} | Error while subscribing: {str(e)}")
                return False
                
            except Exception as e:
                logger.error(f"{self.session_name} | Unknown error while subscribing: {str(e)}")
                return False
                
        finally:
            if not was_connected and (self.client.is_connected if not self.is_pyrogram else self.client.is_connected):
                await self.client.disconnect()
                
        return False

    async def _telethon_mute_and_archive_channel(self, channel_id: int) -> None:
        try:
            await self.client(account.UpdateNotifySettingsRequest(
                peer=InputNotifyPeer(
                    peer=await self.client.get_input_entity(channel_id)
                ),
                settings=InputPeerNotifySettings(
                    mute_until=2147483647
                )
            ))
            logger.info(f"{self.session_name} | Notifications disabled")
            
            await self.client(folders.EditPeerFolders(
                folder_peers=[
                    raw.InputFolderPeer(
                        peer=await self.client.get_input_entity(channel_id),
                        folder_id=1
                    )
                ]
            ))
            logger.info(f"{self.session_name} | Channel added to archive")
            
        except Exception as e:
            logger.warning(f"{self.session_name} | Error while configuring channel: {str(e)}")

    async def _pyrogram_mute_and_archive_channel(self, channel_id: int) -> None:
        try:
            peer = await self.client.resolve_peer(channel_id)
            
            await self.client.invoke(paccount.UpdateNotifySettings(
                peer=ptypes.InputNotifyPeer(peer=peer),
                settings=ptypes.InputPeerNotifySettings(
                    mute_until=2147483647
                )
            ))
            logger.info(f"{self.session_name} | Notifications disabled")
            
            try:
                await self.client.invoke(
                    pfolders.EditPeerFolders(
                        folder_peers=[
                            ptypes.InputFolderPeer(
                                peer=peer,
                                folder_id=1
                            )
                        ]
                    )
                )
                logger.info(f"{self.session_name} | Channel added to archive")
            except Exception as e:
                logger.warning(f"{self.session_name} | Error while archiving: {str(e)}")
                
        except Exception as e:
            logger.warning(f"{self.session_name} | Error while configuring channel: {str(e)}")

    async def join_chat(self, chat_username: str) -> bool:
        try:
            if not chat_username.startswith('@'):
                chat_username = f"@{chat_username}"

            async with self.lock:
                try:
                    if self.is_pyrogram:
                        if not self.client.is_connected:
                            await self.client.connect()

                        try:
                            await self.client.join_chat(chat_username)
                            logger.info(f"{self.session_name} | Successfully joined chat {chat_username}")

                            chat = await self.client.get_chat(chat_username)
                            peer = await self.client.resolve_peer(chat.id)

                            await self.client.invoke(paccount.UpdateNotifySettings(
                                peer=ptypes.InputNotifyPeer(peer=peer),
                                settings=ptypes.InputPeerNotifySettings(
                                    show_previews=False,
                                    silent=True,
                                    mute_until=2147483647
                                )
                            ))
                            logger.info(f"{self.session_name} | Notifications disabled for chat {chat_username}")

                            return True
                        except Exception as e:
                            logger.error(f"{self.session_name} | Error joining chat (Pyrogram): {str(e)}")
                            return False
                    else:
                        if not self.client.is_connected():
                            await self.client.connect()

                        try:
                            await self.client(channels.JoinChannelRequest(chat_username))
                            logger.info(f"{self.session_name} | Successfully joined chat {chat_username}")

                            entity = await self.client.get_entity(chat_username)
                            await self.client(account.UpdateNotifySettingsRequest(
                                peer=InputNotifyPeer(
                                    peer=await self.client.get_input_entity(entity)
                                ),
                                settings=InputPeerNotifySettings(
                                    show_previews=False,
                                    silent=True,
                                    mute_until=2147483647
                                )
                            ))
                            logger.info(f"{self.session_name} | Notifications disabled for chat {chat_username}")

                            return True
                        except Exception as e:
                            logger.error(f"{self.session_name} | Error joining chat (Telethon): {str(e)}")
                            return False
                finally:
                    if self.is_pyrogram:
                        if self.client.is_connected:
                            await self.client.disconnect()
                    else:
                        if self.client.is_connected():
                            await self.client.disconnect()

        except Exception as e:
            logger.error(f"{self.session_name} | General error joining chat: {str(e)}")
            return False

    async def send_start_command(self, pool_id: str) -> bool:
        try:
            bot_username = "@TheOpenCoin_bot"
            command = f"/start pool_{pool_id}"
            max_retries = 3
            retry_delay = 5
            
            async with self.lock:
                try:
                    if self.is_pyrogram:
                        if not self.client.is_connected:
                            await self.client.connect()
                            
                        for attempt in range(max_retries):
                            try:
                                await self.client.send_message(bot_username, command)
                                peer = await self.client.resolve_peer(bot_username)
                                await self.client.invoke(paccount.UpdateNotifySettings(
                                    peer=ptypes.InputNotifyPeer(peer=peer),
                                    settings=ptypes.InputPeerNotifySettings(
                                        show_previews=False,
                                        silent=True,
                                        mute_until=2147483647
                                    )
                                ))
                                try:
                                    await self.client.invoke(
                                        pfolders.EditPeerFolders(
                                            folder_peers=[
                                                ptypes.InputFolderPeer(
                                                    peer=peer,
                                                    folder_id=1
                                                )
                                            ]
                                        )
                                    )
                                except ValueError as ve:
                                    if "unknown constructor" in str(ve).lower():
                                        logger.warning(f"{self.session_name} | Ignoring unknown constructor error while archiving")
                                        continue
                                    raise
                                except Exception as e:
                                    logger.warning(f"{self.session_name} | Error while archiving bot chat: {str(e)}")
                                return True
                                
                            except ValueError as ve:
                                if "unknown constructor" in str(ve).lower():
                                    if attempt < max_retries - 1:
                                        logger.warning(f"{self.session_name} | Unknown constructor error, retrying in {retry_delay}s...")
                                        await asyncio.sleep(retry_delay)
                                        continue
                                raise
                            except Exception as e:
                                if attempt < max_retries - 1:
                                    logger.error(f"{self.session_name} | Error sending start command (Pyrogram), retrying: {str(e)}")
                                    await asyncio.sleep(retry_delay)
                                    continue
                                raise
                                
                        logger.error(f"{self.session_name} | Failed after {max_retries} retries")
                        return False
                        
                    else:
                        if not self.client.is_connected():
                            await self.client.connect()
                            
                        try:
                            entity = await self.client.get_input_entity(bot_username)
                            await self.client.send_message(entity, command)
                            await self.client.edit_folder([entity], folder=1) 
                            return True
                        except Exception as e:
                            logger.error(f"{self.session_name} | Error sending start command (Telethon): {str(e)}")
                            return False
                finally:
                    if self.is_pyrogram:
                        if self.client.is_connected:
                            await self.client.disconnect()
                    else:
                        if self.client.is_connected():
                            await self.client.disconnect()
                            
        except Exception as e:
            logger.error(f"{self.session_name} | General error sending start command: {str(e)}")
            return False
