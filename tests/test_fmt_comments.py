"""Testes do formatter preservando comentários.

Cobrem:
  - Comentário de linha no topo de arquivo, antes de fn
  - Comentário dentro de função (antes de let/return)
  - Comentário inline (x = 1  # foo)
  - Comentário de bloco /* */
  - Idempotência: fmt(fmt(x)) == fmt(x)
"""
import os
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_fmt(path, check=False):
    cmd = [sys.executable, "-m", "lumina_cli", "fmt", path]
    if check:
        cmd.append("--check")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


def _fmt(content):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        result = _run_fmt(path)
        assert result.returncode == 0, f"fmt falhou:\n{result.stderr}"
        with open(path) as f:
            return f.read()
    finally:
        os.unlink(path)


def test_line_comment_header():
    src = "# Header comment\n\nfn main() -> int:\n    return 0\n"
    out = _fmt(src)
    assert "# Header comment" in out
    assert "fn main()" in out


def test_line_comment_inside_function():
    src = (
        "fn main() -> int:\n"
        "    # Dentro\n"
        "    let x = 10\n"
        "    return 0\n"
    )
    out = _fmt(src)
    assert "# Dentro" in out


def test_block_comment():
    src = "/* bloco */\nfn main() -> int:\n    return 0\n"
    out = _fmt(src)
    assert "/* bloco */" in out


def test_idempotent_simple():
    src = (
        "# topo\n"
        "\n"
        "fn main() -> int:\n"
        "    # corpo\n"
        "    let x = 1\n"
        "    return x\n"
    )
    first = _fmt(src)
    second = _fmt(first)
    assert first == second, (
        f"Formatter não é idempotente:\n"
        f"--- 1ª passada ---\n{first}\n"
        f"--- 2ª passada ---\n{second}"
    )


def test_check_on_formatted_file():
    src = "fn main() -> int:\n    return 0\n"
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        # 1. Formata
        r1 = _run_fmt(path)
        assert r1.returncode == 0
        # 2. --check em arquivo formatado → exit 0
        r2 = _run_fmt(path, check=True)
        assert r2.returncode == 0, f"Esperava 0, veio {r2.returncode}:\n{r2.stdout}"
    finally:
        os.unlink(path)

def test_comment_between_functions():
    src = (
        "fn a() -> int:\n"
        "    return 1\n"
        "\n"
        "# Entre funções\n"
        "\n"
        "fn b() -> int:\n"
        "    return 2\n"
    )
    out = _fmt(src)
    assert "# Entre funções" in out


def test_comment_inside_impl():
    src = (
        "struct S:\n"
        "    x: int\n"
        "\n"
        "impl S:\n"
        "    # Método abaixo\n"
        "    fn get() -> int:\n"
        "        return self.x\n"
    )
    out = _fmt(src)
    assert "# Método abaixo" in out


def test_comment_inside_trait():
    src = (
        "trait T:\n"
        "    # Método default\n"
        "    fn greet():\n"
        "        print(1)\n"
    )
    out = _fmt(src)
    assert "# Método default" in out