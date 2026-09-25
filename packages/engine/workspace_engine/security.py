"""Loopback request policy, bounded browser sessions, and scoped agent identities."""
import hmac
import secrets
import threading
import time
from http.cookies import SimpleCookie
from .providers import Principal
from .secrets import SecretStore

OWNER_CAPABILITIES=frozenset(('workspace.read','workspace.write','prompts.read','prompts.write','tasks.read','tasks.write','decisions.read','decisions.request','decisions.resolve','company.write','updates.read','updates.write','skills.read','skills.write','skills.report','skills.review','insights.read','knowledge.read','knowledge.commit','filesystem.read','filesystem.write','filesystem.open','search.read','export.read','providers.inspect','ai.read','ai.manage'))
AGENT_CAPABILITIES=frozenset(('workspace.read','tasks.read','prompts.read','skills.read','decisions.read','decisions.request','updates.read','updates.write','search.read'))

class RequestPolicy:
    def __init__(self, port, aliases=()):
        self.authorities={f'localhost:{port}',f'127.0.0.1:{port}',*aliases}
    def allowed(self, method, path, headers):
        hosts=headers.get_all('Host',[]) if hasattr(headers,'get_all') else [headers.get('Host')]
        if len(hosts)!=1 or hosts[0] not in self.authorities:
            return False
        origin=headers.get('Origin')
        if origin and origin!='http://'+hosts[0]:
            return False
        site=headers.get('Sec-Fetch-Site')
        navigation=method=='GET' and path=='/' and headers.get('Sec-Fetch-Mode')=='navigate' and headers.get('Sec-Fetch-Dest')=='document'
        if site not in (None,'none','same-origin') and not navigation:
            return False
        return True

class Sessions:
    def __init__(self, owner='Workspace owner', ttl=1800, agents=None, secrets_store=None, capabilities=None):
        self.owner=owner;self.ttl=ttl;self.sessions={};self.lock=threading.Lock()
        self.agents=agents or {};self.secrets=secrets_store or SecretStore()
        self.capabilities=frozenset(capabilities) if capabilities is not None else OWNER_CAPABILITIES
        if not self.capabilities<=OWNER_CAPABILITIES:
            raise ValueError('Unknown owner capability')
        for spec in self.agents.values():
            if not set(spec.get('capabilities',()))<=OWNER_CAPABILITIES:
                raise ValueError('Unknown agent capability')
            if not isinstance(spec.get('secretRef'),str):
                raise ValueError('Agent identity requires a secret reference')
    def cookie(self, headers):
        cookie=SimpleCookie()
        try:cookie.load(headers.get('Cookie',''))
        except Exception:return None
        return cookie['workspace-session'].value if 'workspace-session' in cookie else None
    def issue(self, headers):
        current=self.cookie(headers);now=time.monotonic()
        with self.lock:
            self.sessions={key:value for key,value in self.sessions.items() if value[1]>now}
            if current in self.sessions:
                return current,self.sessions[current][0]
            if len(self.sessions)>=256:
                raise PermissionError('Session limit reached')
            key=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
            self.sessions[key]=(csrf,now+self.ttl)
            return key,csrf
    def principal(self, headers, write=False):
        authorization=headers.get('Authorization','')
        if authorization:
            if headers.get('Origin') or headers.get('Sec-Fetch-Site') or not authorization.startswith('Bearer '):
                raise PermissionError('Agent credentials cannot be used by browser requests')
            supplied=authorization[7:]
            for name,spec in self.agents.items():
                expected=self.secrets.get(spec['secretRef'])
                if expected and hmac.compare_digest(expected,supplied):
                    return Principal(name,frozenset(spec.get('capabilities',AGENT_CAPABILITIES)),True)
            raise PermissionError('Agent identity was not recognized')
        key=self.cookie(headers)
        with self.lock:
            session=self.sessions.get(key)
            if not session or session[1]<=time.monotonic():
                raise PermissionError('Session expired. Reload to reconnect; your draft is kept.')
            if write and (not headers.get('Origin') or not hmac.compare_digest(session[0],headers.get('X-Workspace-Token',''))):
                raise PermissionError('This request could not be verified')
        return Principal(self.owner,self.capabilities)
