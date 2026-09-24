"""A read-only, loopback-only launcher for local SKILL.md packages."""

from workspace_engine.adapters.skill_video import VIDEO_TYPES, MAX_VIDEO, read_video, information as video_information

from workspace_engine.adapters.skill_images import IMAGE_TYPES, MAX_IMAGE, read_image, information

from workspace_engine.skill_identity import identity, package_revision
import argparse

import hashlib

import json

import mimetypes

import os

import re

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pathlib import Path

from urllib.parse import parse_qs, unquote, urlsplit

APP = Path(__file__).resolve().parent

MAX_FILE = 1_000_000

TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".sh", ".css", ".html", ".toml", ".csv", ".tmpl"}

SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv"}

def read_text(path):
    if path.stat().st_size > MAX_FILE:
        raise ValueError("File exceeds the 1 MB reading limit")
    return path.read_bytes().decode("utf-8")

def metadata(text, fallback):
    """Read common YAML scalar frontmatter without executing YAML tags."""
    name, description = fallback.replace("-", " ").replace("_", " "), ""
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if match:
        lines = match[1].splitlines()
        for i, line in enumerate(lines):
            field = re.match(r"^(name|description):\s*(.*)$", line)
            if not field:
                continue
            key, value = field.groups()
            if value in (">", "|", ">-", "|-"):
                parts = []
                for next_line in lines[i + 1:]:
                    if next_line and not next_line[0].isspace():
                        break
                    parts.append(next_line.strip())
                value = " ".join(parts)
            value = value.strip().strip("'\"")
            if key == "description":
                description = value
            elif value:
                name = value
    body = text[match.end():] if match else text
    heading = re.search(r"^#\s+(.+)$", body, re.M)
    if heading:
        name = heading[1].strip()
    return name, description, body

class DuplicateSkillIdentity(ValueError):
    pass

class Catalog:
    def __init__(self, config):
        self.config = config
        self.items = {}
        self.warnings = []
        self.refresh()

    def refresh(self):
        items, warnings = {}, []
        for spec in self.config.get("roots", []):
            root = Path(spec["path"]).expanduser()
            label = spec.get("label", root.name)
            if not root.is_dir():
                warnings.append(f"{label}: folder unavailable")
                continue
            root = root.resolve()
            registry = root / "skills.json"
            registered = {}
            if registry.is_file() and not registry.is_symlink():
                try: registered = {r["name"]: r for r in json.loads(registry.read_text()).get("skills", [])}
                except (ValueError, KeyError, TypeError): warnings.append(label + ": invalid registry")
            for directory, folders, names in os.walk(root, followlinks=False):
                folders[:] = sorted(n for n in folders if n not in SKIP and not n.startswith(".") and not (Path(directory) / n).is_symlink())
                if "SKILL.md" not in names:
                    continue
                path = Path(directory) / "SKILL.md"
                if path.is_symlink():
                    continue
                key = hashlib.sha256(str(path).encode()).hexdigest()[:20]
                if key in items:
                    continue
                try:
                    text = read_text(path)
                    name, description, _ = metadata(text, path.parent.name)
                    ident = identity(path)
                    key = ident["id"]
                    if key in items: raise DuplicateSkillIdentity("Duplicate skill identity; reconcile the copied package")
                    shortcut = spec.get("shortcuts", {}).get(path.parent.name, "")
                    display = spec.get("display", {}).get(path.parent.name, {})
                    items[key] = {**ident, "active": registered.get(str(path.parent.relative_to(root)), {}).get("active", True), "revision": package_revision(path), "id": key, "name": name, "description": description,
                                  "label": display.get("label", name), "group": display.get("group", ""),
                                  "order": float(display.get("order", 1000000)),
                                  "source": label, "folder": path.parent.name,
                                  "shortcut": shortcut.lower(), "_path": path}
                except DuplicateSkillIdentity:
                    raise
                except (OSError, UnicodeError, ValueError):
                    warnings.append(f"{label} / {path.parent.name}: could not read SKILL.md")
        self.items = items
        self.warnings = warnings

    def resolve(self, key):
        if key in self.items: return key
        matches = [k for k,v in self.items.items() if key in v.get("aliases", [])]
        if len(matches) == 1: return matches[0]
        raise FileNotFoundError("Skill not found")

    def listing(self):
        return {"skills": [{k: v for k, v in item.items() if not k.startswith("_")} for item in self.items.values() if item.get("active", True)],
                "warnings": self.warnings, "review_url": self.config.get("review_url", ""),
                "examples": self.config.get("examples", [])}

    def files(self, key):
        key = self.resolve(key)
        if key not in self.items:
            raise FileNotFoundError("Skill not found. Refresh the library.")
        root = self.items[key]["_path"].parent
        result = []
        for directory, folders, names in os.walk(root, followlinks=False):
            folders[:] = sorted(n for n in folders if n not in SKIP and not n.startswith(".") and not (Path(directory) / n).is_symlink())
            for name in sorted(names):
                path = Path(directory) / name
                if name.startswith(".") or path.is_symlink() or not path.is_file():
                    continue
                try:
                    size = path.stat().st_size
                    result.append({"path": str(path.relative_to(root)), "bytes": size,
                                   "kind": "image" if path.suffix.lower() in IMAGE_TYPES else "video" if path.suffix.lower() in VIDEO_TYPES else "text",
                                   "readable": (path.suffix.lower() in TEXT_SUFFIXES and size <= MAX_FILE) or (path.suffix.lower() in IMAGE_TYPES and size <= MAX_IMAGE) or (path.suffix.lower() in VIDEO_TYPES and size <= MAX_VIDEO)})
                except OSError:
                    continue
        return result

    def document_path(self, key, relative):
        key = self.resolve(key)
        if key not in self.items:
            raise FileNotFoundError("Skill not found. Refresh the library.")
        item = self.items[key]
        root = item["_path"].parent
        # Both catalog entry and document are checked again on every read.
        if any(p.is_symlink() for p in (item["_path"], *item["_path"].parents)):
            raise ValueError("Symbolic links are not served")
        if "\\" in relative or "\x00" in relative:
            raise ValueError("Invalid document path")
        parts = relative.split("/")
        if any(p in ("", ".", "..") or p.startswith(".") for p in parts):
            raise ValueError("Invalid document path")
        path = root.joinpath(*parts)
        for ancestor in [path, *path.parents]:
            if ancestor == root:
                break
            if ancestor.is_symlink():
                raise ValueError("Symbolic links are not served")
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Document is outside the skill")
        return path

    def image_asset(self, key, relative):
        path = self.document_path(key, relative)
        return read_video(path) if path.suffix.lower() in VIDEO_TYPES else read_image(path)

    def document(self, key, relative="SKILL.md"):
        key = self.resolve(key)
        path = self.document_path(key, relative)
        item = self.items[key]
        if path.suffix.lower() in VIDEO_TYPES:
            return video_information(path, relative, key, item["source"])
        if path.suffix.lower() in IMAGE_TYPES:
            return information(path, relative, key, item["source"])
        if path.suffix.lower() not in TEXT_SUFFIXES:
            raise ValueError("Only supported text documents can be opened")
        raw = read_text(path)
        name, description, body = metadata(raw, path.stem) if path.suffix.lower() == ".md" else (path.name, "", raw)
        if relative == "SKILL.md":
            name, description = item["name"], item["description"]
        return {"id": key, "name": name, "description": description, "text": raw,
                "body": body, "file": relative, "source": item["source"],
                "path": str(path), "sha256": hashlib.sha256(raw.encode()).hexdigest()}

