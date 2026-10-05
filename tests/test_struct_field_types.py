"""Type check em campos de struct literal.

Cobre:
  - tipo correto (ok)
  - tipo errado (erro)
  - int → float (promoção permitida)
  - campo com tipo str recebendo int (erro)
  - campo com ptr recebendo none (permitido)
"""
import os
import pathlib
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _build(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        return subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def _run(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r1 = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        assert r1.returncode == 0, f"Build falhou:\n{r1.stdout}\n{r1.stderr}"
        binary = path[:-3]
        r2 = subprocess.run([binary], capture_output=True, text=True, timeout=timeout)
        return r2.stdout
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


# ============================================================
# Caminho felizes
# ============================================================
def test_all_fields_correct():
    src = (
        'struct P:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = P { x: 1, y: 2 }\n'
        '    print(p.x, p.y)\n'
        '    return 0\n'
    )
    assert "1 2" in _run(src)


def test_int_to_float_promotion():
    src = (
        'struct P:\n'
        '    x: float\n'
        '    y: float\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = P { x: 1, y: 2 }\n'
        '    print(p.x)\n'
        '    return 0\n'
    )
    r = _build(src)
    assert r.returncode == 0, f"int→float deveria ser permitido:\n{r.stdout}"


def test_none_for_ptr_field():
    src = (
        'struct Node:\n'
        '    data: ptr\n'
        '    next: ptr\n'
        '\n'
        'fn main() -> int:\n'
        '    let n = Node { data: none, next: none }\n'
        '    return 0\n'
    )
    r = _build(src)
    assert r.returncode == 0, f"none para ptr deveria ser permitido:\n{r.stdout}"


# ============================================================
# Erros esperados
# ============================================================
def test_str_into_int_field():
    src = (
        'struct P:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = P { x: "texto", y: 2 }\n'
        '    return 0\n'
    )
    r = _build(src)
    assert r.returncode != 0, "str em campo int deveria falhar"
    assert "Tipo inválido para campo 'x'" in r.stdout


def test_int_into_str_field():
    src = (
        'struct P:\n'
        '    nome: str\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = P { nome: 42 }\n'
        '    return 0\n'
    )
    r = _build(src)
    assert r.returncode != 0, "int em campo str deveria falhar"
    assert "Tipo inválido para campo 'nome'" in r.stdout


def test_float_into_int_field():
    """float → int NÃO é permitido implicitamente (trunca)."""
    src = (
        'struct P:\n'
        '    x: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = P { x: 3.14 }\n'
        '    return 0\n'
    )
    r = _build(src)
    assert r.returncode != 0, "float em campo int deveria falhar"
    assert "Tipo inválido para campo 'x'" in r.stdout
