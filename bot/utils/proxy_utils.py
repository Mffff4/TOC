import os
import aiohttp
from aiohttp_proxy import ProxyConnector
from collections import Counter
from python_socks import ProxyType
from shutil import copyfile
from better_proxy import Proxy
from bot.config import settings
from bot.utils import logger
from random import shuffle

PROXY_TYPES = {
    'socks5': ProxyType.SOCKS5,
    'socks4': ProxyType.SOCKS4,
    'http': ProxyType.HTTP,
    'https': ProxyType.HTTP
}


def get_proxy_type(proxy_type: str) -> ProxyType:
    return PROXY_TYPES.get(proxy_type.lower())


def to_telethon_proxy(proxy: Proxy) -> dict:
    return {
        'proxy_type': get_proxy_type(proxy.protocol),
        'addr': proxy.host,
        'port': proxy.port,
        'username': proxy.login,
        'password': proxy.password
    }


def to_pyrogram_proxy(proxy: Proxy) -> dict:
    return {
        'scheme': proxy.protocol if proxy.protocol != 'https' else 'http',
        'hostname': proxy.host,
        'port': proxy.port,
        'username': proxy.login,
        'password': proxy.password
    }


def get_proxies(proxy_path: str) -> list[str]:
    proxy_template_path = "bot/config/proxies-template.txt"

    if not os.path.isfile(proxy_path):
        copyfile(proxy_template_path, proxy_path)
        return []

    if settings.USE_PROXY:
        with open(file=proxy_path, encoding="utf-8-sig") as file:
            return list({Proxy.from_str(proxy=row.strip()).as_url for row in file if row.strip() and
                         not row.strip().startswith('type')})
    return []


def get_unused_proxies(accounts_config: dict, proxy_path: str) -> list[str]:
    proxies_count = Counter([v.get('proxy') for v in accounts_config.values() if v.get('proxy')])
    all_proxies = get_proxies(proxy_path)
    return [proxy for proxy in all_proxies if proxies_count.get(proxy, 0) < settings.SESSIONS_PER_PROXY]


async def check_proxy(proxy: str) -> bool:
    if not proxy or not isinstance(proxy, str):
        logger.warning(f"Invalid proxy format: {proxy}")
        return False
        
    try:
        if '://' not in proxy:
            logger.warning(f"No protocol specified in proxy: {proxy}")
            return False
            
        protocol = proxy.split('://')[0].lower()
        if protocol not in PROXY_TYPES:
            logger.warning(f"Unsupported proxy protocol: {protocol}")
            return False
            
        urls = [
            'https://api.ipify.org'
        ]
        
        try:
            proxy_conn = ProxyConnector.from_url(proxy)
        except ValueError as e:
            logger.warning(f"Invalid proxy URL format: {proxy} - {str(e)}")
            return False
        except Exception as e:
            logger.warning(f"Error creating proxy connector: {proxy} - {str(e)}")
            return False
    
        try:
            async with aiohttp.ClientSession(connector=proxy_conn, timeout=aiohttp.ClientTimeout(15)) as session:
                for url in urls:
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                ip = await response.text()
                                if ip and len(ip.split('.')) == 4:
                                    logger.success(f"Successfully connected to proxy via {url}. IP: {ip}")
                                    return True
                                else:
                                    logger.warning(f"Invalid IP response from {url}: {ip}")
                                    continue
                    except aiohttp.ClientError as e:
                        logger.warning(f"Connection error with {url}: {str(e)}")
                        continue
                    except Exception as e:
                        logger.warning(f"Unexpected error with {url}: {str(e)}")
                        continue
                
                logger.warning(f"Proxy {proxy} failed all connection attempts")
                return False
                
        except Exception as e:
            logger.warning(f"Proxy {proxy} didn't respond: {str(e)}")
            return False
        finally:
            if proxy_conn and not proxy_conn.closed:
                proxy_conn.close()
                
    except Exception as e:
        logger.warning(f"Unexpected error checking proxy {proxy}: {str(e)}")
        return False


async def get_proxy_chain(path: str) -> tuple[str | None, str | None]:
    try:
        with open(path, 'r') as file:
            proxy = file.read().strip()
            return proxy, to_telethon_proxy(Proxy.from_str(proxy))
    except Exception:
        logger.error(f"Failed to get proxy for proxy chain from '{path}'")
        return None, None


async def get_working_proxy(accounts_config: dict, current_proxy: str | None) -> str | None:
    if current_proxy and await check_proxy(current_proxy):
        return current_proxy

    from bot.utils import PROXIES_PATH
    unused_proxies = get_unused_proxies(accounts_config, PROXIES_PATH)
    shuffle(unused_proxies)
    for proxy in unused_proxies:
        if await check_proxy(proxy):
            return proxy

    return None
