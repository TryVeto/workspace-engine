"""All external operations cross a named, capability-checked adapter boundary."""
from dataclasses import dataclass
from typing import Any, Iterable, Protocol

class FilesProvider(Protocol):
    def inventory(self, query: str = '', offset: int = 0) -> dict: ...
    def mutate(self, request: dict) -> dict: ...
class TaskProvider(Protocol):
    def list(self) -> list[dict]: ...
    def edit(self, request: dict) -> dict: ...
class CalendarProvider(Protocol):
    def events(self, start: str, end: str) -> list[dict]: ...
class MessageProvider(Protocol):
    def messages(self, cursor: str | None = None) -> dict: ...
class SearchProvider(Protocol):
    def search(self, query: str, limit: int = 30) -> list[dict]: ...
class AIProvider(Protocol):
    def stream(self, messages: list[dict]) -> Iterable[str]: ...
class StorageProvider(Protocol):
    def put(self, path, key: str, digest: str, mime: str): ...
    def read(self, key: str, limit: int | None = None) -> bytes: ...

@dataclass(frozen=True)
class Principal:
    name: str
    capabilities: frozenset[str]
    agent: bool = False
    def require(self, capability):
        if capability not in self.capabilities:
            raise PermissionError('This identity does not have '+capability)

class ProviderRegistry:
    def __init__(self):
        self._providers = {}
        self._operations = {}
    def register(self, name, provider, operations):
        if name in self._providers:
            raise ValueError('Provider already registered')
        for operation, capability in operations.items():
            if not callable(getattr(provider, operation, None)) or not isinstance(capability,str):
                raise ValueError('Invalid provider operation')
        self._providers[name] = provider
        self._operations[name] = dict(operations)
    def call(self, principal, provider, operation, *args, **kwargs):
        capability = self._operations.get(provider, {}).get(operation)
        if not capability:
            raise LookupError('Provider operation unavailable')
        principal.require(capability)
        return getattr(self._providers[provider],operation)(*args,**kwargs)
    def describe(self):
        return {name:dict(operations) for name,operations in self._operations.items()}
