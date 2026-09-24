"""SQLite connections close deterministically; durable data never lives in the checkout."""
import os
import sqlite3
from pathlib import Path

class Connection(sqlite3.Connection):
    def __exit__(self, kind, value, traceback):
        try:
            return super().__exit__(kind, value, traceback)
        finally:
            self.close()

def connect(path, timeout=15, **kwargs):
    if str(path) != ':memory:':
        target=Path(path).expanduser().resolve()
        if any((parent/'.git').exists() for parent in target.parents):
            raise ValueError('Databases must remain outside Git working trees')
    connection = sqlite3.connect(path, timeout=timeout, factory=Connection, **kwargs)
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA busy_timeout=15000')
    connection.execute('PRAGMA synchronous=FULL')
    if str(path) != ':memory:' and Path(path).exists():
        os.chmod(path, 0o600)
    return connection

def private_directory(path, repository=None):
    path = Path(path).expanduser().resolve()
    if repository and path.is_relative_to(Path(repository).resolve()):
        raise ValueError('Runtime data must be outside the engine repository')
    if any((parent / '.git').exists() for parent in (path, *path.parents)):
        raise ValueError('Runtime data must be outside every Git working tree')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


def sync_directory(path):
    descriptor=os.open(str(path),os.O_RDONLY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
