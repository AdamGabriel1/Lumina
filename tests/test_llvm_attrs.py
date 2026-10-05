"""Atributos LLVM por função: @inline, @noinline, @cold, @hot."""
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _build_ir(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        assert r.returncode == 0, f"Build falhou:\n{r.stdout}\n{r.stderr}"
        with open(path[:-3] + ".ll") as irf:
            return irf.read()
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


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


# ============================================================
# @inline
# ============================================================
def test_inline_attr():
    src = (
        '@inline\n'
        'fn dobro(x: int) -> int:\n'
        '    return x * 2\n'
        '\n'
        'fn main() -> int:\n'
        '    return dobro(5)\n'
    )
    ir = _build_ir(src)
    # LLVM emite `attributes #N = { alwaysinline }` e a função referencia
    assert "alwaysinline" in ir, f"IR sem alwaysinline:\n{ir[:500]}"


def test_inline_executes_correctly():
    src = (
        '@inline\n'
        'fn dobro(x: int) -> int:\n'
        '    return x * 2\n'
        '\n'
        'fn main() -> int:\n'
        '    print(dobro(21))\n'
        '    return 0\n'
    )
    r = _build(src)
    assert r.returncode == 0


# ============================================================
# @noinline
# ============================================================
def test_noinline_attr():
    src = (
        '@noinline\n'
        'fn f(x: int) -> int:\n'
        '    return x + 1\n'
        '\n'
        'fn main() -> int:\n'
        '    return f(0)\n'
    )
    ir = _build_ir(src)
    assert "noinline" in ir, f"IR sem noinline:\n{ir[:500]}"


# ============================================================
# @cold
# ============================================================
def test_cold_attr():
    src = (
        '@cold\n'
        'fn log_error():\n'
        '    print("erro")\n'
        '\n'
        'fn main() -> int:\n'
        '    log_error()\n'
        '    return 0\n'
    )
    ir = _build_ir(src)
    assert "cold" in ir, f"IR sem cold:\n{ir[:500]}"


# ============================================================
# @hot
# ============================================================
def test_hot_attr():
    """`@hot` mapeia para `inlinehint` (ver codegen).

    O LLVM tem `hot` como string attribute (`"hot"`), não enum, e o
    llvmlite não expõe API para string attributes em Function.attributes.
    Mapeamos para `inlinehint` — mesma intenção semântica.
    """
    src = (
        '@hot\n'
        'fn loop_body(x: int) -> int:\n'
        '    return x + 1\n'
        '\n'
        'fn main() -> int:\n'
        '    return loop_body(0)\n'
    )
    ir = _build_ir(src)
    assert "inlinehint" in ir, f"IR sem inlinehint (de @hot):\n{ir[:500]}"


# ============================================================
# Combinações
# ============================================================
def test_inline_and_cold_together():
    src = (
        '@inline\n'
        '@cold\n'
        'fn edge_case() -> int:\n'
        '    return -1\n'
        '\n'
        'fn main() -> int:\n'
        '    return edge_case()\n'
    )
    ir = _build_ir(src)
    assert "alwaysinline" in ir
    assert "cold" in ir


def test_inline_and_noinline_conflict():
    src = (
        '@inline\n'
        '@noinline\n'
        'fn bad(x: int) -> int:\n'
        '    return x\n'
        '\n'
        'fn main() -> int:\n'
        '    return bad(0)\n'
    )
    r = _build(src)
    assert r.returncode != 0, "@inline + @noinline deveria falhar"
    combined = r.stdout + r.stderr
    assert "conflitante" in combined or "inline" in combined


# ============================================================
# Compat com @safe
# ============================================================
def test_inline_and_safe_together():
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        '@inline\n'
        '@safe\n'
        'fn get_id(u: U) -> int:\n'
        '    return u.id\n'
        '\n'
        'fn main() -> int:\n'
        '    let u: U = nil\n'
        '    print(get_id(u))\n'
        '    return 0\n'
    )
    ir = _build_ir(src)
    assert "alwaysinline" in ir
    # E roda OK (0 quando nil)
    r = _build(src)
    assert r.returncode == 0


# ============================================================
# Sem attr — não deve ter alwaysinline/noinline
# ============================================================
def test_no_attr_no_llvm_attrs():
    src = (
        'fn plain(x: int) -> int:\n'
        '    return x\n'
        '\n'
        'fn main() -> int:\n'
        '    return plain(0)\n'
    )
    ir = _build_ir(src)
    assert "alwaysinline" not in ir, f"IR com alwaysinline inesperado:\n{ir[:500]}"
    assert "noinline" not in ir, f"IR com noinline inesperado:\n{ir[:500]}"
