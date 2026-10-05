"""Verifica que a Boehm GC está ativa no codegen padrão.

Sem o fix, o codegen emitia `malloc` (libc) em vez de `GC_malloc`,
e nunca chamava `GC_init()`. O `-lgc` no linker era decorativo.

Estes testes inspecionam o IR e o comportamento em runtime.

NOTA: os testes de IR só fazem sentido se a libgc estiver instalada
no sistema. Se não estiver, o build nativo falha — que é exatamente
o comportamento esperado (bom aviso).

NOTA 2: llvmlite emite nomes de função com aspas (`@"GC_init"`),
por isso os asserts usam uma versão normalizada do IR.
"""
import os
import pathlib
import re
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _build(src, extra_flags=None):
    """Compila e retorna o IR gerado (str)."""
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        cmd = [sys.executable, "-m", "lumina_cli", "build", path]
        if extra_flags:
            cmd.extend(extra_flags)
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        assert result.returncode == 0, f"Build falhou:\n{result.stdout}\n{result.stderr}"
        ir_path = path[:-3] + ".ll"
        with open(ir_path) as irf:
            return irf.read()
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def _norm(ir):
    """Normaliza o IR para matching robusto.

    llvmlite emite `@"GC_init"()` (com aspas) e `phi  i1` (2 espaços).
    Esta função remove aspas e colapsa whitespace para que os asserts
    possam usar a forma "limpa".
    """
    return " ".join(ir.replace('"', "").split())


# ============================================================
# Inspeção do IR
# ============================================================
def test_default_build_uses_gc_malloc():
    src = (
        'fn get_size() -> int:\n'
        '    return 10\n'
        '\n'
        'fn main() -> int:\n'
        '    let n = get_size()\n'
        '    let buf = alloc(n)\n'
        '    return 0\n'
    )
    ir = _build(src)
    assert "GC_malloc" in ir
    assert "declare i8* @malloc" not in _norm(ir)


def test_default_build_calls_gc_init():
    src = (
        'fn main() -> int:\n'
        '    return 0\n'
    )
    ir = _build(src)
    norm = _norm(ir)
    assert "GC_init" in norm, (
        f"IR não chama GC_init() — GC nunca inicializa.\n{ir}"
    )
    # GC_init deve ser CHAMADA dentro de main (call void @GC_init)
    assert "call void @GC_init" in norm, (
        f"GC_init declarado mas não chamado em main.\n{ir}"
    )


def test_no_gc_flag_uses_plain_malloc():
    src = (
        'fn get_size() -> int:\n'
        '    return 10\n'
        '\n'
        'fn main() -> int:\n'
        '    let n = get_size()\n'
        '    let buf = alloc(n)\n'
        '    return 0\n'
    )
    ir = _build(src, extra_flags=["--no-gc"])
    norm = _norm(ir)
    assert "GC_malloc" not in norm
    assert "GC_init" not in norm
    assert "declare i8* @malloc" in norm


def test_gc_init_comes_before_first_allocation():
    src = (
        'fn get_size() -> int:\n'
        '    return 10\n'
        '\n'
        'fn main() -> int:\n'
        '    let n = get_size()\n'
        '    let buf = alloc(n)\n'
        '    buf[0] = 42\n'
        '    print(buf[0])\n'
        '    return 0\n'
    )
    ir = _build(src)
    norm = _norm(ir)
    gc_init_pos = norm.find("call void @GC_init")
    assert gc_init_pos >= 0
    m = re.search(r"call i8\* @GC_malloc", norm)
    assert m is not None
    assert gc_init_pos < m.start()


# ============================================================
# Comportamento em runtime
# ============================================================
def test_gc_program_runs():
    """Programa que aloca e usa memória deve rodar normalmente."""
    src = (
        'fn main() -> int:\n'
        '    let buf = alloc(10)\n'
        '    buf[0] = 1\n'
        '    buf[1] = 2\n'
        '    print(buf[0], buf[1])\n'
        '    return 0\n'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r1 = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r1.returncode == 0, f"Build falhou:\n{r1.stdout}\n{r1.stderr}"
        binary = path[:-3]
        r2 = subprocess.run([binary], capture_output=True, text=True)
        assert "1 2" in r2.stdout
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def test_gc_handles_many_allocations():
    """Aloca 10k strings concatenadas — sem GC, seria lento demais
    ou estouraria memória em alguns ambientes."""
    src = (
        'fn main() -> int:\n'
        '    mut i = 0\n'
        '    mut total = 0\n'
        '    while i < 10000:\n'
        '        let s = "x" + i\n'
        '        total += len(s)\n'
        '        i += 1\n'
        '    print("done", total)\n'
        '    return 0\n'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r1 = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
        )
        assert r1.returncode == 0, f"Build falhou:\n{r1.stdout}\n{r1.stderr}"
        binary = path[:-3]
        r2 = subprocess.run([binary], capture_output=True, text=True, timeout=30)
        assert "done" in r2.stdout
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)

# PATCH: removida a duplicata de `test_default_build_uses_gc_malloc`
# que existia no final do arquivo. O pytest rodava o mesmo teste 2x,
# inflando a contagem total. Esta versão tem 6 testes.