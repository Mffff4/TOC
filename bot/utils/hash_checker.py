import json
import aiohttp
import hashlib
import re
import time
import asyncio
import ssl
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from bot.utils import logger
from bot.config.config import settings
import os
from datetime import datetime

@dataclass
class Endpoint:
    path: str
    method: str
    required_params: Optional[List[str]] = None

@dataclass
class CaptchaType:
    type: str
    context: Optional[Dict] = None
    file: Optional[str] = None

class HashChecker:
    def __init__(self):
        self.gist_url = "https://gist.githubusercontent.com/Mffff4/e3ec4b2fa5d161955c1c8b28315f1af8/raw/toc-hash.json"
        self._js_url = "https://miniapp.theopencoin.xyz/_next/static/chunks/4746-d0b3fc8077cd6e71.js"
        self._base_url = "https://miniapp.theopencoin.xyz"
        self._pages = [
            f"{self._base_url}/",
            f"{self._base_url}/vote",
            f"{self._base_url}/pools"
        ]
        self._http_client: Optional[aiohttp.ClientSession] = None
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
        
        self._api_patterns = [
            r'["\']([^"\']*\/api\/v1\/[^"\']+)["\']',
            r'fetch\s*\([^)]*\/api\/v1\/[^)]+\)',
            r'axios\s*\.[a-z]+\s*\([^)]*\/api\/v1\/[^)]+\)',
            r'\/api\/v1\/(?:proposals?|votes?)\/[^"\']+',
            r'\/api\/v1\/pools\/[^"\']+',
        ]
        
        self._method_patterns = [
            (r'method:\s*["\']POST["\']', 'POST'),
            (r'method:\s*["\']PUT["\']', 'PUT'),
            (r'method:\s*["\']DELETE["\']', 'DELETE'),
            (r'method:\s*["\']GET["\']', 'GET'),
            (r'\.post\s*\(', 'POST'),
            (r'\.put\s*\(', 'PUT'),
            (r'\.delete\s*\(', 'DELETE'),
            (r'\.get\s*\(', 'GET'),
            (r'post:\s*async', 'POST'),
            (r'put:\s*async', 'PUT'),
            (r'delete:\s*async', 'DELETE'),
            (r'get:\s*async', 'GET'),
            (r'body:\s*JSON\.stringify', 'POST'),
            (r'params:', 'GET'),
        ]
        
        self._endpoint_method_map = {
            '/api/v1/pools/join-invoice': 'POST',
            '/api/v1/pools/leave': 'POST',
            '/api/v1/blocks/start-mining': 'POST',
            '/api/v1/captures/verify': 'POST',
            '/api/v1/proposals/vote': 'POST',
            '/api/v1/users/check-x': 'GET',
            '/api/v1/users/check-community': 'GET',
            '/api/v1/users/stats': 'GET',
            '/api/v1/pools/user-pool': 'GET',
            '/api/v1/pools': 'GET',
            '/api/v1/proposals': 'GET',
            '/api/v1/blocks/latest': 'GET'
        }
        
        self._json_patterns = [
            r'JSON\.stringify\(\{([^}]+)\}\)',
            r'body:\s*JSON\.stringify\(\{([^}]+)\}\)',
            r'data:\s*\{([^}]+)\}',
            r'params:\s*\{([^}]+)\}'
        ]
        
        self._endpoint_params_map = {
            '/api/v1/pools/join-invoice': ['miningPoolId', 'poolName'],
            '/api/v1/pools/leave': ['miningPoolId'],
            '/api/v1/blocks/start-mining': ['blockId'],
            '/api/v1/captures/verify': ['captureType', 'captureContext'],
            '/api/v1/proposals/vote': ['proposalId', 'voteForProposal'],
            '/api/v1/blocks/user-results': ['afterBlockId', 'currentBlockId']
        }
        
        self._vote_patterns = [
            r'(?:async\s+)?function\s+vote\w*\s*\([^)]*\)\s*{([^}]+)}',
            r'vote\w*:\s*(?:async\s+)?function\s*\([^)]*\)\s*{([^}]+)}',
            r'const\s+vote\w*\s*=\s*(?:async\s+)?\([^)]*\)\s*=>\s*{([^}]+)}',
            r'handle\w*Vote\w*\s*=\s*(?:async\s+)?\([^)]*\)\s*=>\s*{([^}]+)}',
            r'function\s+\w*Vote\w*\s*\([^)]*\)\s*{([^}]+)}',
            r'\/api\/v1\/(?:proposals?|votes?)\/[^"\']+',
            r'fetch\s*\([^)]*\/api\/v1\/(?:proposals?|votes?)[^)]+\)',
            r'axios\s*\.[a-z]+\s*\([^)]*\/api\/v1\/(?:proposals?|votes?)[^)]+\)',
            r'params:\s*{\s*[^}]*proposal[^}]*}',
            r'params:\s*{\s*[^}]*vote[^}]*}'
        ]
        
        self._pool_patterns = [
            r'\/api\/v1\/pools\/[^"\']+',
            r'fetch\s*\([^)]*\/api\/v1\/pools[^)]+\)',
            r'axios\s*\.[a-z]+\s*\([^)]*\/api\/v1\/pools[^)]+\)',
            r'params:\s*{\s*[^}]*pool[^}]*}',
            r'(?:async\s+)?function\s+(?:join|leave|get)Pool\w*\s*\([^)]*\)\s*{([^}]+)}',
            r'pool:\s*{\s*([^}]+)\s*}',
            r'["\']([^"\']*\/api\/v1\/pools\/[^"\'?]+)\?([^"\']+)["\']',
            r'params:\s*{\s*(?:pool|mining)[^}]*}[^}]*["\']([^"\']*\/api\/v1\/[^"\']+)["\']',
            r'\/api\/v1\/pools\/join-invoice',
            r'\/api\/v1\/pools\/leave',
            r'\/api\/v1\/pools\/user-pool'
        ]
        
        self.found_captcha_types: List[CaptchaType] = []
        
        self._captcha_patterns = [
            r'["\']([A-Z0-9_]+_V1)["\']',
            r'captureType:\s*["\']([A-Z0-9_]+_V1)["\']',
            r'type:\s*["\']([A-Z0-9_]+_V1)["\']',
            r'case\s*["\']([A-Z0-9_]+_V1)["\']',
            r'if\s*\(\s*type\s*===?\s*["\']([A-Z0-9_]+_V1)["\']'
        ]
        
        self._captcha_context_patterns = [
            r'context:\s*({[^}]+})',
            r'captureContext:\s*({[^}]+})',
            r'{\s*["\']?a["\']?\s*:\s*(\d+)\s*,\s*["\']?b["\']?\s*:\s*(\d+)\s*}',
            r'{\s*["\']?value["\']?\s*:\s*(\d+)\s*}'
        ]
        
    async def _init_client(self) -> None:
        if not self._http_client or self._http_client.closed:
            connector = aiohttp.TCPConnector(ssl=self._ssl_context)
            self._http_client = aiohttp.ClientSession(
                connector=connector,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'sec-ch-ua': '"Chromium";v="131", "Not_A Brand";v="24"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"macOS"',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
    async def get_gist_hash(self) -> Optional[str]:
        try:
            headers = {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            params = {
                '_': str(int(time.time()))
            }
            async with self._http_client.get(self.gist_url, headers=headers, params=params, ssl=self._ssl_context) as response:
                if response.status == 200:
                    content = await response.text()
                    try:
                        file_data = json.loads(content)
                        hash_value = file_data.get("current_hash")
                        if hash_value:
                            return ''.join(c for c in hash_value if c.isprintable())
                        return None
                    except json.JSONDecodeError:
                        return None
                return None
        except Exception:
            return None

    async def _download_js(self) -> Optional[str]:
        try:
            pages = [
                "https://miniapp.theopencoin.xyz/",
                "https://miniapp.theopencoin.xyz/vote",
                "https://miniapp.theopencoin.xyz/pools"
            ]
            
            all_js_files = set()
            for page_url in pages:
                try:
                    async with self._http_client.get(page_url, ssl=self._ssl_context) as response:
                        if response.status == 200:
                            html_content = await response.text()
                            all_js_files.update(re.findall(r'src="([^"]+\.js)"', html_content))
                            chunk_ids = re.findall(r'chunks/([^"]+)"', html_content)
                            for chunk in chunk_ids:
                                if chunk.endswith('.js'):
                                    all_js_files.add(f"/_next/static/chunks/{chunk}")
                                else:
                                    all_js_files.add(f"/_next/static/chunks/{chunk}.js")
                except Exception:
                    continue
            
            all_content = []
            
            for js_file in all_js_files:
                if not js_file.startswith('http'):
                    js_file = f"https://miniapp.theopencoin.xyz{js_file}"
                
                headers = {
                    'Accept': 'text/javascript,application/javascript,application/ecmascript,application/x-ecmascript,*/*;q=0.9',
                    'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Referer': 'https://miniapp.theopencoin.xyz/',
                    'sec-fetch-dest': 'script',
                    'sec-fetch-mode': 'no-cors',
                    'sec-fetch-site': 'same-origin'
                }
                
                try:
                    async with self._http_client.get(js_file, headers=headers, ssl=self._ssl_context) as response:
                        if response.status == 200:
                            content = await response.text()
                            if 'capture' in content or 'captcha' in content:
                                await self._analyze_js_file(js_file, content)
                            all_content.append(content)
                except Exception:
                    continue
            
            if not all_content:
                return None
                
            return "\n".join(all_content)
            
        except Exception:
            return None

    def _normalize_path(self, path: str) -> str:
        path = path.strip('/"\'')
        path = path.strip()
        
        if not path.startswith('/'):
            path = '/' + path
            
        path = path.split('?')[0]
        
        path = re.sub(r':\([^)]+\)', '', path)
        path = re.sub(r'\([^)]*\)', '', path)
        path = re.sub(r':\w+', '', path)
        path = re.sub(r',\s*\(\s*\)', '', path)
        path = re.sub(r',\s*[^/,]+(?=[,)]|$)', '', path)
        path = re.sub(r'\.[a-zA-Z]+\s*\([^)]*\)', '', path)
        
        path = re.sub(r'["\']', '', path)
        path = re.sub(r'\s+', '', path)
        path = re.sub(r',$', '', path)
        
        path = re.sub(r'/+', '/', path)
        
        path = re.sub(r'[^/a-zA-Z0-9_-]+', '', path)
        
        return path

    def _determine_method_from_context(self, context: str, path: str) -> str:
        if path in self._endpoint_method_map:
            return self._endpoint_method_map[path]
        
        for pattern, method in self._method_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return method
        
        if any(word in context.lower() for word in ['create', 'add', 'join', 'start', 'submit', 'vote']):
            return 'POST'
        if any(word in context.lower() for word in ['update', 'edit', 'modify']):
            return 'PUT'
        if any(word in context.lower() for word in ['delete', 'remove', 'leave']):
            return 'DELETE'
        if any(word in context.lower() for word in ['get', 'fetch', 'load', 'check']):
            return 'GET'
        
        return 'GET'

    def _extract_params_from_context(self, context: str, path: str) -> Optional[List[str]]:
        params = set()
        
        if path in self._endpoint_params_map:
            params.update(self._endpoint_params_map[path])
        
        for pattern in self._json_patterns:
            for match in re.finditer(pattern, context, re.MULTILINE | re.DOTALL):
                content = match.group(1)
                param_matches = re.findall(r'(\w+):', content)
                params.update(param_matches)
        
        url_params = re.findall(r'\?([^"\']+)["\']', context)
        for param_str in url_params:
            param_pairs = param_str.split('&')
            for pair in param_pairs:
                if '=' in pair:
                    param_name = pair.split('=')[0]
                    params.add(param_name)
        
        return sorted(list(params)) if params else None

    def _is_valid_endpoint(self, path: str) -> bool:
        if not path.startswith('/api/v1/'):
            return False
            
        if any(x in path for x in ['(', ')', '.', ',', ':', 'fetch']):
            return False
            
        if not re.match(r'^/api/v1/[a-zA-Z0-9/-]+$', path):
            return False
            
        return True

    def _extract_endpoints(self, js_content: str) -> List[Endpoint]:
        endpoints = []
        seen_endpoints = set()
        
        all_patterns = (
            [(p, 'api') for p in self._api_patterns] +
            [(p, 'vote') for p in self._vote_patterns] +
            [(p, 'pool') for p in self._pool_patterns]
        )
        
        for pattern, pattern_type in all_patterns:
            for match in re.finditer(pattern, js_content, re.MULTILINE | re.DOTALL):
                context = js_content[max(0, match.start() - 200):min(len(js_content), match.end() + 200)]
                
                if pattern_type == 'api':
                    path = match.group(0) if '/api/v1/' in match.group(0) else match.group(1)
                    paths = [path] if '/api/v1/' in path else []
                else:
                    paths = re.findall(r'["\']([^"\']*\/api\/v1\/[^"\']+)["\']', context)
                
                for path in paths:
                    path = self._normalize_path(path)
                    
                    if not self._is_valid_endpoint(path):
                        continue
                        
                    method = self._determine_method_from_context(context, path)
                    params = self._extract_params_from_context(context, path)
                    
                    endpoint_key = f"{method}:{path}"
                    if endpoint_key not in seen_endpoints:
                        seen_endpoints.add(endpoint_key)
                        endpoints.append(Endpoint(
                            path=path,
                            method=method,
                            required_params=params
                        ))
        
        endpoints.sort(key=lambda x: (x.method, x.path))
        return endpoints
    
    def _get_captcha_description(self, captcha_type: str) -> str:
        if captcha_type == "SUMM_V1":
            return "Сложение двух чисел (a + b)"
        elif captcha_type == "STARS_V1":
            return "Подсчет количества звезд (a)"
        elif captcha_type == "MULTIPLY_V1":
            return "Умножение двух чисел (a * b)"
        elif captcha_type == "SUBTRACT_V1":
            return "Вычитание двух чисел (a - b)"
        else:
            return "Неизвестный тип капчи"
            
    async def _analyze_js_file(self, js_file: str, content: str) -> None:
        v1_matches = re.finditer(r'["\']([A-Z0-9_]+_V1)["\']', content)
        for match in v1_matches:
            captcha_type = match.group(1)
            if not captcha_type:
                continue
            
            start_pos = max(0, match.start() - 500)
            end_pos = min(len(content), match.end() + 500)
            context_area = content[start_pos:end_pos]
            
            context = None
            context_patterns = [
                rf'context:\s*({{\s*[^}}]+\s*}})',
                rf'captureContext:\s*({{\s*[^}}]+\s*}})',
                r'{\s*["\']?a["\']?\s*:\s*(\d+)\s*,\s*["\']?b["\']?\s*:\s*(\d+)\s*}',
                r'{\s*["\']?value["\']?\s*:\s*(\d+)\s*}',
                r'context:\s*({[^}]+})',
                r'captureContext:\s*({[^}]+})',
                rf'type:\s*["\']?{re.escape(captcha_type)}["\']?\s*,\s*context:\s*({{\s*[^}}]+\s*}})',
                rf'if\s*\(\s*type\s*===?\s*["\']?{re.escape(captcha_type)}["\']?\s*\)\s*{{\s*.*?context:\s*({{\s*[^}}]+\s*}})',
                rf'case\s*["\']?{re.escape(captcha_type)}["\']?:\s*{{.*?context:\s*({{\s*[^}}]+\s*}})',
                rf'verify(?:Capture|Result)\s*\([^)]*["\']?{re.escape(captcha_type)}["\']?[^)]*\)\s*{{\s*.*?context:\s*({{\s*[^}}]+\s*}})',
                rf'if\s*\([^)]*["\']?{re.escape(captcha_type)}["\']?[^)]*\)\s*{{\s*.*?context:\s*({{\s*[^}}]+\s*}})'
            ]
            
            for ctx_pattern in context_patterns:
                ctx_match = re.search(ctx_pattern, context_area, re.DOTALL)
                if ctx_match:
                    try:
                        if len(ctx_match.groups()) == 1:
                            context = json.loads(ctx_match.group(1).replace("'", '"'))
                        else:
                            context = {'a': int(ctx_match.group(1)), 'b': int(ctx_match.group(2))} if len(ctx_match.groups()) == 2 else {'value': int(ctx_match.group(1))}
                    except Exception:
                        context = ctx_match.group(1)
                    break
            
            captcha = CaptchaType(
                type=captcha_type,
                context=context,
                file=os.path.basename(js_file)
            )
            
            if not any(c.type == captcha_type for c in self.found_captcha_types):
                self.found_captcha_types.append(captcha)

    def generate_report(self, gist_hash: str, current_hash: str, endpoints: List[Endpoint]) -> Dict:
        hash_status = {
            "gist_hash": gist_hash,
            "current_hash": current_hash,
            "match": gist_hash == current_hash if gist_hash and current_hash else False
        }
        
        endpoints_info = [{
            "path": e.path,
            "method": e.method,
            "required_params": e.required_params
        } for e in endpoints]
        
        captcha_info = [{
            "type": c.type,
            "context": c.context,
            "file": c.file,
            "description": self._get_captcha_description(c.type)
        } for c in self.found_captcha_types]
        
        results = {
            "hash_check": hash_status,
            "endpoints": endpoints_info,
            "captcha_types": captcha_info,
            "timestamp": datetime.now().isoformat()
        }
        
        with open("hash_check_results.json", 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        logger.info("\n✅ Results saved to hash_check_results.json")
        return results

    async def get_current_hash(self) -> Optional[str]:
        try:
            js_content = await self._download_js()
            if not js_content:
                return None
                
            endpoints = self._extract_endpoints(js_content)
            if not endpoints:
                return None
            
            endpoints.sort(key=lambda x: (x.method, x.path))
            
            hash_components = []
            
            if settings.DEBUG_HASH:
                print("\n=== Found Endpoints ===")
            
            for endpoint in endpoints:
                component = f"{endpoint.method}:{endpoint.path}"
                if endpoint.required_params:
                    component += ":" + ",".join(sorted(endpoint.required_params))
                hash_components.append(component)
                if settings.DEBUG_HASH:
                    print(f"Endpoint: {component}")
            
            if settings.DEBUG_HASH and self.found_captcha_types:
                print("\n=== Found Captcha Types ===")
            
            for captcha in sorted(self.found_captcha_types, key=lambda x: x.type):
                component = f"CAPTCHA:{captcha.type}"
                if captcha.context:
                    if isinstance(captcha.context, dict):
                        context_str = json.dumps(captcha.context, sort_keys=True)
                    else:
                        context_str = str(captcha.context)
                    component += f":{context_str}"
                hash_components.append(component)
                if settings.DEBUG_HASH:
                    print(f"Captcha: {component}")
            
            if settings.DEBUG_HASH:
                print("\n=== Hash String ===")
                print("|".join(sorted(hash_components)))
                print("==================")
            
            hash_str = "|".join(sorted(hash_components))
            return hashlib.sha256(hash_str.encode()).hexdigest()
            
        except Exception:
            return None
    
    async def check_hash(self) -> Tuple[bool, Optional[Dict]]:
        if not settings.CHECK_API_HASH:
            return True, None
            
        try:
            await self._init_client()
            
            gist_hash = await self.get_gist_hash()
            if not gist_hash:
                return False, None
                
            current_hash = await self.get_current_hash()
            if not current_hash:
                return False, None
                
            if settings.DEBUG_HASH:
                print("\n=== Hash Check ===")
                print(f"Gist hash:    {gist_hash}")
                print(f"Current hash: {current_hash}")
                print(f"Match: {'✅' if gist_hash.strip() == current_hash.strip() else '❌'}")
                print("=================")
                
            if gist_hash.strip() != current_hash.strip():
                return False, None
                
            return True, None
            
        except Exception:
            return False, None
            
        finally:
            if self._http_client and not self._http_client.closed:
                await self._http_client.close()
                self._http_client = None

hash_checker = HashChecker() 
