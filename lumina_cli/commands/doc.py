"""`lumina doc` — gera documentação (html/md/json) a partir de comentários `##`."""
import glob
import json
import os

from ..utils import Color, paint, info, success


def cmd_doc(output_format="html", output_path=None):
    info(f"📚 Gerando documentação ({output_format})...")
    docs_data = _collect_docs()

    if output_format == "json":
        content = _render_doc_json(docs_data)
        default_path = os.path.join("docs", "index.json")
    elif output_format == "md":
        content = _render_doc_md(docs_data)
        default_path = os.path.join("docs", "index.md")
    else:
        content = _render_doc_html(docs_data)
        default_path = os.path.join("docs", "index.html")

    dest = output_path or default_path
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dest, "w") as f:
        f.write(content)

    success(f"✅ Documentação gerada em: {paint(dest, Color.BOLD + Color.BRIGHT_CYAN)}")


def _collect_docs():
    docs_data = []
    for filepath in glob.glob("**/*.lm", recursive=True):
        if "lumina_modules" in filepath or filepath.startswith("std/"):
            continue
        try:
            with open(filepath, "r") as f:
                lines = f.readlines()
        except Exception:
            continue

        current_doc = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                current_doc.append(stripped[3:])
            elif stripped.startswith("##"):
                current_doc.append(stripped[2:])
            elif stripped == "" or stripped.startswith("#"):
                current_doc = []
            elif current_doc and (
                stripped.startswith("fn ") or
                stripped.startswith("struct ") or
                stripped.startswith("enum ") or
                stripped.startswith("trait ")
            ):
                if stripped.startswith("fn "):
                    decl = stripped.replace("fn ", "").replace(" -> ", " ⟶ ")
                    dtype = "Function"
                elif stripped.startswith("struct "):
                    decl = stripped
                    dtype = "Struct"
                elif stripped.startswith("enum "):
                    decl = stripped
                    dtype = "Enum"
                else:
                    decl = stripped
                    dtype = "Trait"

                docs_data.append({
                    "file": filepath,
                    "type": dtype,
                    "decl": decl,
                    "doc": "\n".join(current_doc),
                })
                current_doc = []
    return docs_data


def _render_doc_html(docs_data):
    html = """<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Lumina Documentation</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 2rem; background-color: #f8f9fa; }
        h1 { border-bottom: 2px solid #ddd; padding-bottom: 0.5rem; color: #2c3e50; }
        .item { background: #fff; padding: 1.5rem; margin-bottom: 1rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .decl { font-family: "Fira Code", "Courier New", monospace; font-size: 1.1rem; color: #d6336c; font-weight: bold; }
        .type { display: inline-block; padding: 0.2rem 0.5rem; background: #e9ecef; border-radius: 4px; font-size: 0.8rem; color: #495057; margin-left: 0.5rem; }
        .doc { margin-top: 0.5rem; color: #495057; }
        .file { font-size: 0.8rem; color: #6c757d; font-style: italic; margin-top: 1rem; }
    </style>
</head>
<body>
    <h1>🌟 Lumina Standard Library</h1>
"""
    if not docs_data:
        html += "<p>Nenhuma documentação encontrada. Use '##' acima de funções, structs ou enums.</p>"
    else:
        for item in docs_data:
            html += f"""
    <div class="item">
        <div class="decl">{item['decl']} <span class="type">{item['type']}</span></div>
        <div class="doc">{item['doc']}</div>
        <div class="file">Definido em: {item['file']}</div>
    </div>
"""
    html += """
</body>
</html>"""
    return html


def _render_doc_md(docs_data):
    lines = ["# 🌟 Lumina Standard Library", ""]
    if not docs_data:
        lines.append("_Nenhuma documentação encontrada. Use `##` acima de funções, structs ou enums._")
        return "\n".join(lines)

    by_type = {}
    for item in docs_data:
        by_type.setdefault(item["type"], []).append(item)

    for dtype in ("Function", "Struct", "Enum", "Trait"):
        if dtype not in by_type:
            continue
        heading = {"Function": "Funções", "Struct": "Structs",
                   "Enum": "Enums", "Trait": "Traits"}[dtype]
        lines.append(f"## {heading}")
        lines.append("")
        for item in by_type[dtype]:
            lines.append(f"### `{item['decl']}`")
            lines.append("")
            if item["doc"]:
                for doc_line in item["doc"].split("\n"):
                    lines.append(doc_line)
                lines.append("")
            lines.append(f"_Definido em: `{item['file']}`_")
            lines.append("")
    return "\n".join(lines)


def _render_doc_json(docs_data):
    payload = {
        "title": "Lumina Standard Library",
        "count": len(docs_data),
        "items": docs_data,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
