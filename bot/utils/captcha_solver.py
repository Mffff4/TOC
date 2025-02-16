from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List, Union
import hashlib
import json
import base64
import re
import aiohttp
import asyncio
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import padding
import time


@dataclass
class CaptchaSolution:
    type: str
    answer: Union[int, str]
    raw_context: Optional[dict] = None


class CaptchaSolver:
    _instance = None
    _key: Optional[str] = None
    _key_timestamp: float = 0
    _key_cache_time = 300
    _js_content_cache: Dict[str, Tuple[str, float]] = {}
    _js_cache_time = 60
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CaptchaSolver, cls).__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        self._base_url = "https://miniapp.theopencoin.xyz"
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _fetch_js(self, url: str) -> Optional[str]:
        current_time = time.time()
        if url in self._js_content_cache:
            content, timestamp = self._js_content_cache[url]
            if current_time - timestamp < self._js_cache_time:
                return content
        
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    self._js_content_cache[url] = (content, current_time)
                    return content
        except Exception as e:
            print(f"Error fetching {url}: {e}")
        return None
    
    async def _find_key_in_page(self) -> Optional[str]:
        try:
            url = f"{self._base_url}/_next/static/chunks/app/page-"
            session = await self._get_session()
            async with session.get(self._base_url) as response:
                if response.status != 200:
                    return None
                html = await response.text()
            match = re.search(r'page-([a-f0-9]+)\.js', html)
            if not match:
                return None
            js_url = f"{url}{match.group(1)}.js"
            content = await self._fetch_js(js_url)
            if content and 'NqlWSO25af' in content:
                return 'NqlWSO25af'
        except Exception as e:
            print(f"Error finding key: {e}")
        return None
    
    async def _get_key(self) -> Optional[str]:
        current_time = time.time()
        if self._key and (current_time - self._key_timestamp) < self._key_cache_time:
            return self._key
        self._key = await self._find_key_in_page()
        if self._key:
            self._key_timestamp = current_time
        return self._key
    
    def _split_capture(self, capture: str) -> Tuple[str, str, str]:
        try:
            part1, part2, part3 = capture.split(":")
            return part1, part2, part3
        except ValueError:
            raise ValueError("Invalid capture format")
    
    def _hex_to_bytes(self, hex_str: str) -> bytes:
        result = []
        for i in range(0, len(hex_str), 2):
            result.append(int(hex_str[i:i+2], 16))
        return bytes(result)
    
    def _prepare_key(self, key: str) -> bytes:
        padded = key.encode().ljust(32, b'0')
        return padded[:32]
    
    def _parse_decrypted(self, decrypted: bytes) -> Optional[CaptchaSolution]:
        try:
            text = decrypted.decode()
            parts = text.split('-')
            if len(parts) >= 2:
                if parts[0] == 'STARS_V1':
                    return CaptchaSolution(
                        type='STARS_V1',
                        answer=int(parts[1]),
                        raw_context={'stars': int(parts[1])}
                    )
                elif parts[0] == 'SUMM_V1':
                    a, b = int(parts[1]), int(parts[2])
                    return CaptchaSolution(
                        type='SUMM_V1',
                        answer=a + b,
                        raw_context={'a': a, 'b': b}
                    )
                elif parts[0] == 'SLIDER_V1':
                    return CaptchaSolution(
                        type='SLIDER_V1',
                        answer=int(parts[1]),
                        raw_context={'slider_value': int(parts[1])}
                    )
            try:
                data = json.loads(text)
                if isinstance(data, dict) and 'type' in data and 'context' in data:
                    context = data['context']
                    if isinstance(context, dict) and 'a' in context and 'b' in context:
                        return CaptchaSolution(
                            type=data['type'],
                            answer=context['a'] + context['b'],
                            raw_context=context
                        )
            except json.JSONDecodeError:
                pass
        except Exception as e:
            print(f"Error parsing: {str(e)}")
        return None
    
    async def solve(self, capture: str) -> Optional[CaptchaSolution]:
        try:
            current_time = time.time()
            if not self._key or (current_time - self._key_timestamp) >= self._key_cache_time:
                key = await self._get_key()
                if not key:
                    raise ValueError("Failed to obtain key for decryption")
            else:
                key = self._key
                
            iv_hex, data1_hex, data2_hex = self._split_capture(capture)
            iv = self._hex_to_bytes(iv_hex)
            data1 = self._hex_to_bytes(data1_hex)
            data2 = self._hex_to_bytes(data2_hex)
            data = bytes([*data1, *data2])
            key_bytes = self._prepare_key(key)
            aesgcm = AESGCM(key_bytes)
            try:
                decrypted = aesgcm.decrypt(iv, data, None)
                result = self._parse_decrypted(decrypted)
                if result:
                    return result
            except Exception as e:
                print(f"Error during decryption: {str(e)}")
                if "decryption failed" in str(e).lower():
                    print("Decryption failed, trying with new key...")
                    self._key = None 
                    return await self.solve(capture)
                return None
        except Exception as e:
            print(f"Error solving captcha: {str(e)}")
            return None
        finally:
            if self._session and not self._session.closed:
                await self._session.close()
        return None


_solver_instance = None


async def solve_captcha(capture: str) -> Optional[CaptchaSolution]:
    global _solver_instance
    if _solver_instance is None:
        _solver_instance = CaptchaSolver()
    return await _solver_instance.solve(capture)
