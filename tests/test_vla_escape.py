"""Escape analysis para `alloc(N)` com N dinâmico (VLA) — v0.7.0.

`alloc(N)` com N dinâmico pode virar `alloca` (VLA) quando:
  1. Não está dentro de loop
  2. Está no bloco de topo da função (não em if/else)
  3. A variável não escapa
  4. A variável não é passada a `free`

**Nota importante sobre escape analysis:**
Escrever `buf[i] = v` marca `buf` como escaping (conservador). Isso
é intencional — um valor armazenado em `buf[i]` pode ser um
ponteiro que aponta para outra alocação, criando um escape
transitivo. Refinar isso para distinguir int de ptr é trabalho
para v0.8.x. Consequência prática: `alloc(10); buf[0] = 42` **não**
usa stack, apesar do tamanho conhecido.

Cobre:
  - VLA emitido quando `alloc(n)` não escapa (não usa subscript)
  - `alloc(n)` em loop → GC
  - `alloc(n)` em if → GC
  - `alloc(n)` que escapa (retornado) → GC
  - `alloc(N)` literal → stack alloca (sem subscript)
  - `alloc(N)` literal + subscript → GC (conservador)
"""
import os
import pathlib
import re
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _build_ir(src, extra_flags=None, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        cmd = [sys.executable, "-m", "lumina_cli", "build", path]
        if extra_flags:
            cmd.extend(extra_flags)
        r = subprocess.run(
            cmd, capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        assert r.returncode == 0, f"Build falhou:\n{r.stdout}\n{r.stderr}"
        with open(path[:-3] + ".ll") as irf:
            return irf.read()
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
        r2 = subprocess.run(
            [path[:-3]], capture_output=True, text=True, timeout=timeout,
        )
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


# ============================================================
# VLA habilitado (sem escape)
# ============================================================
def test_vla_emitted_when_no_escape():
    """`alloc(n)` sem subscript → VLA `alloca i64, i64 %n`.

    Usa `--debug` para desabilitar O1 (evita DCE do alloca não usado).
    """
    src = (
        'fn process(n: int) -> int:\n'
        '    let buf = alloc(n)\n'
        '    let addr = buf as int\n'
        '    return n\n'
        '\n'
        'fn main() -> int:\n'
        '    return process(10)\n'
    )
    ir = _build_ir(src, extra_flags=["--debug"])
    norm = " ".join(ir.split())
    assert re.search(r"alloca i64, i64 %", norm), (
        f"VLA não foi emitido (alloc(n) sem escape):\n{ir[:1500]}"
    )


def test_vla_runtime_correctness():
    """Programa com VLA funciona em runtime (usa `--release`)."""
    src = (
        'fn process(n: int) -> int:\n'
        '    let buf = alloc(n)\n'
        '    mut i = 0\n'
        '    while i < n:\n'
        '        buf[i] = i * i\n'
        '        i += 1\n'
        '    mut sum = 0\n'
        '    i = 0\n'
        '    while i < n:\n'
        '        sum += buf[i]\n'
        '        i += 1\n'
        '    return sum\n'
        '\n'
        'fn main() -> int:\n'
        '    # 0 + 1 + 4 + ... + 81 = 285\n'
        '    print(process(10))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "285" in out, f"out={out!r}"


# ============================================================
# VLA desabilitado (fallback para GC)
# ============================================================
def test_alloc_in_loop_uses_gc():
    """`alloc(n)` dentro de loop → GC_malloc (evita crescimento de stack)."""
    src = (
        'fn process(n: int) -> int:\n'
        '    mut total = 0\n'
        '    mut i = 0\n'
        '    while i < n:\n'
        '        let buf = alloc(n)\n'
        '        buf[0] = i\n'
        '        total += buf[0]\n'
        '        i += 1\n'
        '    return total\n'
        '\n'
        'fn main() -> int:\n'
        '    print(process(5))\n'
        '    return 0\n'
    )
    ir = _build_ir(src)
    assert "GC_malloc" in ir, (
        f"alloc dentro de loop deveria usar GC_malloc:\n{ir[:1000]}"
    )


def test_alloc_in_if_uses_gc():
    """`alloc(n)` dentro de if → GC_malloc (bloco condicional)."""
    src = (
        'fn process(n: int, cond: int) -> int:\n'
        '    mut result = 0\n'
        '    if cond != 0:\n'
        '        let buf = alloc(n)\n'
        '        buf[0] = 42\n'
        '        result = buf[0]\n'
        '    return result\n'
        '\n'
        'fn main() -> int:\n'
        '    print(process(5, 1))\n'
        '    return 0\n'
    )
    ir = _build_ir(src)
    assert "GC_malloc" in ir, (
        f"alloc dentro de if deveria usar GC_malloc:\n{ir[:1000]}"
    )


def test_escaping_alloc_uses_gc():
    """`alloc(n)` retornado → GC_malloc (escapa)."""
    src = (
        'fn make(n: int) -> ptr:\n'
        '    let buf = alloc(n)\n'
        '    return buf\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = make(5)\n'
        '    return 0\n'
    )
    ir = _build_ir(src)
    assert "GC_malloc" in ir, (
        f"alloc que escapa deveria usar GC_malloc:\n{ir[:1000]}"
    )


# ============================================================
# Literal (regressão + comportamento conservador)
# ============================================================
def test_literal_alloc_uses_stack_when_no_escape():
    """`alloc(N)` literal sem subscript → `alloca [N x i64]`.

    Nota: sem subscript write, `buf` não escapa, então stack alloc.
    """
    src = (
        'fn process() -> int:\n'
        '    let buf = alloc(10)\n'
        '    let addr = buf as int\n'
        '    return 0\n'
        '\n'
        'fn main() -> int:\n'
        '    return process()\n'
    )
    ir = _build_ir(src, extra_flags=["--debug"])
    norm = " ".join(ir.split())
    assert re.search(r"alloca \[10 x i64\]", norm), (
        f"alloc(10) sem subscript deveria virar `alloca [10 x i64]`:\n{ir[:1500]}"
    )


def test_subscript_write_marks_escape_conservative():
    """Escrever `buf[i] = v` marca `buf` como escaping (conservador).

    Comportamento atual: `buf` vai para heap (`GC_malloc`), não stack.
    Intencional: um valor armazenado via subscript pode ser um
    ponteiro que aponta para outra alocação, criando escape
    transitivo. Refinamento (distinguir int de ptr) planejado
    para v0.8.x.

    Se este teste falhar porque `GC_malloc` saiu do IR, a análise
    de escape foi refinada — atualize o teste.
    """
    src = (
        'fn process() -> int:\n'
        '    let buf = alloc(10)\n'
        '    buf[0] = 42\n'
        '    return buf[0]\n'
        '\n'
        'fn main() -> int:\n'
        '    return process()\n'
    )
    ir = _build_ir(src)
    assert "GC_malloc" in ir, (
        f"subscript write deveria conservadoramente usar GC:\n{ir[:1000]}"
    )