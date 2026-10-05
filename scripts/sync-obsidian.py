#!/usr/bin/env python3
# scripts/sync-obsidian.py
from pathlib import Path
import shutil

SRC = Path.home() / "github/Lumina"
DST = Path.home() / "Documentos/Obsidian/Dev/Lumina"
SKIP = {".git", "node_modules", "__pycache__", ".venv", "target", ".pytest_cache"}

def frontmatter(rel: Path) -> str:
    parent = rel.parent.as_posix().replace("/", "-")
    tags = "lumina" + (f", {parent}" if parent != "." else "")
    return f"---\nsource: {rel.as_posix()}\ntags: [{tags}]\n---\n\n"

def strip_fm(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text

if DST.exists():
    shutil.rmtree(DST)
DST.mkdir(parents=True, exist_ok=True)

n = 0
for md in SRC.rglob("*.md"):
    if any(p in md.parts for p in SKIP):
        continue
    rel = md.relative_to(SRC)
    dst = DST / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    body = strip_fm(md.read_text(encoding="utf-8"))
    dst.write_text(frontmatter(rel) + body, encoding="utf-8")
    n += 1

print(f"✓ {n} arquivos sincronizados em {DST}")
