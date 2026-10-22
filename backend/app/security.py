import ipaddress, socket
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException, Header
from .config import settings

class Principal:
    def __init__(self,admin=False): self.admin=admin

def principal(authorization: str | None = Header(default=None)):
    token=(authorization or '').removeprefix('Bearer ')
    if token == settings.admin_token: return Principal(True)
    if settings.demo_mode and (token == settings.demo_token or not token): return Principal()
    raise HTTPException(401,'Требуется токен доступа')

def require_admin(p):
    if not p.admin: raise HTTPException(403,'Операция доступна администратору локального стенда')

def assert_company_access(company,p):
    if not p.admin and not company.synthetic:
        raise HTTPException(403,'Официальные данные доступны только локальному администратору')

def validate_url(url: str):
    parts=urlsplit(url)
    host=(parts.hostname or '').lower()
    allowed={h.strip() for h in settings.news_hosts.split(',')}
    if parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None,443) or host not in allowed:
        raise ValueError('Разрешены только HTTPS-ссылки на подключённые новостные источники')
    addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Внутренние и служебные адреса запрещены')
    return url

async def fetch_public(url:str, max_bytes=2_000_000):
    validate_url(url)
    # No redirects, proxies, cookies, credentials or arbitrary domains. DNS-rebinding
    # residual is documented; production additionally requires an outbound allowlist.
    async with httpx.AsyncClient(timeout=15,follow_redirects=False,trust_env=False) as client:
        async with client.stream('GET',url,headers={'User-Agent':'AlfaInsight-Hackathon/1.0'}) as response:
            response.raise_for_status()
            if response.status_code in range(300,400): raise ValueError('Перенаправления не разрешены')
            kind=response.headers.get('content-type','')
            if not any(t in kind for t in ['text/','xml','rss']): raise ValueError('Ожидается текстовый документ')
            body=bytearray()
            async for part in response.aiter_bytes():
                body.extend(part)
                if len(body)>max_bytes: raise ValueError('Источник превышает лимит 2 МБ')
            return bytes(body)
