"""Portable identity and provenance; paths remain locations, never identities."""
import hashlib, json, re
from pathlib import Path

ID = re.compile(r"^skl_[A-Za-z0-9_-]{8,80}$")
FIELDS = {"id", "aliases", "source", "upstream", "upstream_revision", "imported_at",
          "license", "local_changes", "based_on", "imported_sha256"}

def identity(path):
    path = Path(path)
    legacy = hashlib.sha256(str(path).encode()).hexdigest()[:20]
    file = path.parent / "workspace-skill.json"
    if not file.exists():
        return {"id": legacy, "stable": False, "aliases": []}
    if file.is_symlink() or file.stat().st_size > 16384:
        raise ValueError("Invalid skill identity")
    record = json.loads(file.read_text())
    if not isinstance(record, dict) or set(record) - FIELDS or not ID.fullmatch(record.get("id", "")):
        raise ValueError("Invalid skill identity")
    aliases = record.get("aliases", [])
    if not isinstance(aliases, list) or len(aliases) > 100 or any(not isinstance(x, str) or len(x)>100 for x in aliases):
        raise ValueError("Invalid identity aliases")
    result = {**record, "stable": True, "aliases": list(dict.fromkeys([legacy, *aliases]))}
    current = hashlib.sha256(path.read_bytes()).hexdigest()
    if record.get("imported_sha256"):
        result["local_changes"] = current != record["imported_sha256"]
    return result

def package_revision(path):
    """Digest readable authored package contents, excluding identity location aliases."""
    root = Path(path).parent
    digest = hashlib.sha256()
    for file in sorted(root.rglob("*")):
        if any(part.startswith(".") for part in file.relative_to(root).parts) or file.is_symlink():
            continue
        if not file.is_file() or file.name == "workspace-skill.json":
            continue
        if file.suffix.lower() not in (".md", ".txt", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".sh", ".tmpl"):
            continue
        if file.stat().st_size > 1_000_000:
            continue
        digest.update(str(file.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
