"""Configuração de `[link]` e compilação de extra_objects (.c/.cpp/.o)."""
import os
import re
import subprocess

try:
    import tomllib
except ImportError:
    tomllib = None

from ..utils import Color, paint, warn
from .errors import report_error


def load_link_config(entry_file=None):
    """Carrega config de [link] do lumina.toml apropriado.

    Prioridade:
      1. Se entry_file dado: procura <entry_file sem .lm>.toml (sidecar).
      2. Fallback: procura ./lumina.toml.
    """
    config_path = None
    if entry_file:
        sidecar = re.sub(r'\.lm$', '.toml', entry_file)
        if os.path.exists(sidecar):
            config_path = sidecar
        elif os.path.exists("lumina.toml"):
            config_path = "lumina.toml"
    elif os.path.exists("lumina.toml"):
        config_path = "lumina.toml"

    if not config_path or tomllib is None:
        return {}

    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
    except Exception:
        return {}

    link = config.get("link", {})
    return {
        "libs": list(link.get("libs", [])),
        "extra_objects": list(link.get("extra_objects", [])),
        "target": link.get("target"),
        "extra_flags": list(link.get("extra_flags", [])),
    }


def compile_extra_objects(extra_objects, extra_flags=None):
    """Compila cada extra_object (.c/.cpp/.cc) para .o e retorna a lista."""
    obj_paths = []
    has_cpp = False

    filtered_flags = []
    for f in (extra_flags or []):
        if f in ("--wasm", "--no-gc", "--debug", "--release"):
            continue
        if f.startswith("--target="):
            filtered_flags.append("-target")
            filtered_flags.append(f.split("=", 1)[1])
        else:
            filtered_flags.append(f)

    for src in extra_objects:
        if not os.path.exists(src):
            warn(f"⚠️  extra_object não encontrado: {paint(src, Color.MUTED)}")
            continue

        is_cpp = src.endswith(('.cpp', '.cc', '.cxx', '.C'))
        compiler = "clang++" if is_cpp else "clang"
        obj_out = os.path.splitext(src)[0] + ".o"

        cmd = [compiler, "-O2", "-c", src, "-o", obj_out] + filtered_flags

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            obj_paths.append(obj_out)
            if is_cpp:
                has_cpp = True
        except subprocess.CalledProcessError as e:
            err = (e.stderr or b"").decode("utf-8", errors="replace")[:200]
            report_error(f"Falha ao compilar {src}: {err}")

    return obj_paths, has_cpp
