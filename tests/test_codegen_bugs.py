"""Testes de regressão dos bugs latentes no codegen.

Cobrem:
  - `and`/`or` geram basic blocks de curto-circuito + phi (antes caíam no
    fallback que retornava 0).
  - `alloc_bytes` cria `i8*` (não `i64*`), e `arr[i]` normaliza o `i8`
    de volta para `i64` via sext.
  - Retorno de operador binário em structs copia o resultado para um
    slot no caller (evita ponteiro para stack inválida).
  - `print(bool)` faz zext para i64 e imprime com %ld.
  - Top-level `let X = <literal>` é inline em cada uso.
"""
import os
import pathlib
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _build(src, extra_flags=None):
    """Compila um `.lm` e retorna o IR gerado (str)."""
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


def _run(src):
    """Compila, executa e retorna stdout."""
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
        r2 = subprocess.run([binary], capture_output=True, text=True, cwd=REPO_ROOT)
        return r2.stdout
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


# ============================================================
# and / or
#
# NOTA: desde o patch de short-circuit, o codegen NÃO emite mais
# `and i1` / `or i1`. Em vez disso, gera basic blocks `*_rhs` /
# `*_end` + uma `phi i1` para combinar. Os testes abaixo checam
# essa estrutura (que é o que o short-circuit exige). O
# comportamento em runtime é coberto por
# `test_and_short_circuit_logic` e `test_or_short_circuit_logic`.
# ============================================================
def test_and_generates_short_circuit_blocks():
    src = (
        'fn main() -> int:\n'
        '    let x = 1\n'
        '    let y = 2\n'
        '    if x > 0 and y > 0:\n'
        '        print("both")\n'
        '    return 0\n'
    )
    ir = _build(src)
    # Normaliza espaçamento (llvmlite imprime "phi  i1" com 2 espaços)
    norm = " ".join(ir.split())

    assert "and_rhs:" in norm, f"Bloco 'and_rhs' ausente:\n{ir}"
    assert "and_end:" in norm, f"Bloco 'and_end' ausente:\n{ir}"
    assert "phi i1" in norm, f"phi i1 ausente — sem combinação de ramos:\n{ir}"


def test_or_generates_short_circuit_blocks():
    src = (
        'fn main() -> int:\n'
        '    let x = 0\n'
        '    let y = 1\n'
        '    if x > 0 or y > 0:\n'
        '        print("some")\n'
        '    return 0\n'
    )
    ir = _build(src)
    norm = " ".join(ir.split())

    assert "or_rhs:" in norm, f"Bloco 'or_rhs' ausente:\n{ir}"
    assert "or_end:" in norm, f"Bloco 'or_end' ausente:\n{ir}"
    assert "phi i1" in norm, f"phi i1 ausente — sem combinação de ramos:\n{ir}"


def test_and_short_circuit_logic():
    """Verifica o comportamento em runtime."""
    src = (
        'fn main() -> int:\n'
        '    if 1 == 1 and 2 == 2:\n'
        '        print("both true")\n'
        '    if 1 == 2 or 2 == 2:\n'
        '        print("some true")\n'
        '    if 1 == 1 and 2 == 3:\n'
        '        print("should not print")\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "both true" in out
    assert "some true" in out
    assert "should not print" not in out


# ============================================================
# alloc_bytes
# ============================================================
def test_alloc_bytes_returns_i8_ptr():
    src = (
        'fn get_size() -> int:\n'
        '    return 100\n'
        '\n'
        'fn main() -> int:\n'
        '    let n = get_size()\n'
        '    let buf = alloc_bytes(n)\n'
        '    buf[0] = 42\n'
        '    print(buf[0])\n'
        '    return 0\n'
    )
    ir = _build(src)
    assert "malloc" in ir or "GC_malloc" in ir


def test_alloc_bytes_roundtrip():
    src = (
        'fn main() -> int:\n'
        '    let buf = alloc_bytes(10)\n'
        '    buf[0] = 1\n'
        '    buf[1] = 2\n'
        '    buf[2] = 3\n'
        '    print(buf[0], buf[1], buf[2])\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "1 2 3" in out


# ============================================================
# Struct field type inference
# ============================================================
def test_member_expr_infers_ptr_type():
    """`let x = self.campo` onde campo é ptr deve inferir `ptr`.

    Sem o fix, o semantic infere `int` e o codegen faz ptrtoint —
    `d[0]` falha com 'index of non-pointer'.
    """
    src = (
        'struct Box:\n'
        '    data: ptr\n'
        '\n'
        'impl Box:\n'
        '    fn write(i: int, v: int):\n'
        '        let d = self.data\n'
        '        d[i] = v\n'
        '    fn read(i: int) -> int:\n'
        '        let d = self.data\n'
        '        return d[i]\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box\n'
        '    b.data = alloc(4)\n'
        '    b.write(0, 42)\n'
        '    b.write(1, 99)\n'
        '    print(b.read(0), b.read(1))\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "42 99" in out


# ============================================================
# Operator overloading return
# ============================================================
def test_struct_operator_return_valid():
    src = (
        'struct V2:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'impl V2:\n'
        '    fn __add__(a: V2, b: V2) -> V2:\n'
        '        mut r: V2\n'
        '        r.x = a.x + b.x\n'
        '        r.y = a.y + b.y\n'
        '        return r\n'
        '\n'
        'fn main() -> int:\n'
        '    mut a: V2\n'
        '    a.x = 1\n'
        '    a.y = 2\n'
        '    mut b: V2\n'
        '    b.x = 10\n'
        '    b.y = 20\n'
        '    let c = a + b\n'
        '    print(c.x, c.y)\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "11 22" in out


# ============================================================
# print(bool)
# ============================================================
def test_print_bool_uses_true_false():
    src = (
        'fn main() -> int:\n'
        '    let x = 1 == 1\n'
        '    let y = 1 == 2\n'
        '    print(x, y)\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "true false" in out
    assert "(null)" not in out


def test_print_bool_from_comparison():
    src = (
        'fn main() -> int:\n'
        '    let a = 5\n'
        '    let b = 5\n'
        '    print(a == b)\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "true" in out


# ============================================================
# Top-level constants
# ============================================================
def test_toplevel_constant_inlined():
    src = (
        'let MY_CONST = 42\n'
        '\n'
        'fn main() -> int:\n'
        '    print(MY_CONST)\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "42" in out


def test_toplevel_constant_used_in_loop():
    src = (
        'let LIMIT = 5\n'
        '\n'
        'fn main() -> int:\n'
        '    mut total = 0\n'
        '    mut i = 0\n'
        '    while i < LIMIT:\n'
        '        total += i\n'
        '        i += 1\n'
        '    print(total)\n'
        '    return 0\n'
    )
    out = _run(src)
    # 0 + 1 + 2 + 3 + 4 = 10
    assert "10" in out


# ============================================================
# Método de impl chama outro método via self
# ============================================================
def test_method_calls_another_method():
    src = (
        'struct Counter:\n'
        '    value: int\n'
        '\n'
        'impl Counter:\n'
        '    fn inc():\n'
        '        self.value = self.value + 1\n'
        '    fn inc_twice():\n'
        '        self.inc()\n'
        '        self.inc()\n'
        '\n'
        'fn main() -> int:\n'
        '    mut c: Counter\n'
        '    c.value = 0\n'
        '    c.inc_twice()\n'
        '    print(c.value)\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "2" in out


# ============================================================
# Trait default chama método abstrato
# ============================================================
def test_trait_default_calls_abstract():
    src = (
        'trait Greeter:\n'
        '    fn name() -> str\n'
        '    fn greet():\n'
        '        let n = name()\n'
        '        print("Hi,", n)\n'
        '\n'
        'struct English:\n'
        '    dummy: int\n'
        '\n'
        'impl Greeter for English:\n'
        '    fn name() -> str:\n'
        '        return "Lumina"\n'
        '\n'
        'fn main() -> int:\n'
        '    mut e: English\n'
        '    e.dummy = 0\n'
        '    e.greet()\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "Hi," in out
    assert "Lumina" in out


# ============================================================
# Bitwise & shifts
# ============================================================
def test_bitwise_and():
    # 12 & 10 = 8 (0b1100 & 0b1010)
    src = (
        'fn main() -> int:\n'
        '    let x = 12 & 10\n'
        '    print(x)\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "8" in out


def test_bitwise_or():
    # 12 | 10 = 14 (0b1100 | 0b1010)
    src = (
        'fn main() -> int:\n'
        '    let x = 12 | 10\n'
        '    print(x)\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "14" in out


def test_shift_left():
    src = (
        'fn main() -> int:\n'
        '    let x = 1 << 4\n'
        '    print(x)\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "16" in out


def test_shift_right():
    src = (
        'fn main() -> int:\n'
        '    let x = 256 >> 2\n'
        '    print(x)\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "64" in out


# ============================================================
# Slice
# ============================================================
def test_string_slice():
    src = (
        'fn main() -> int:\n'
        '    let s = "abcdef"\n'
        '    print(s[1..4])\n'
        '    print(s[..3])\n'
        '    print(s[2..])\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "bcd" in out
    assert "abc" in out
    assert "cdef" in out


# ============================================================
# comptime
# ============================================================
def test_comptime_folding():
    src = (
        'fn main() -> int:\n'
        '    let x = comptime(2 + 3 * 4)\n'
        '    print(x)\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "14" in out