"""TCO para mutual recursion (Sprint 8c).

Antes: `f` chama `g` em tail position → stack cresce.
Agora: SCCs de tail calls viram dispatchers; mutual recursion
também roda em stack constante.
"""
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(src, timeout=60):
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
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


# ============================================================
# is_even / is_odd — caso clássico
# ============================================================
def test_is_even_odd_1m():
    """1M iterações via mutual recursion — sem TCO estouraria."""
    src = (
        'fn is_even(n: int) -> int:\n'
        '    if n == 0:\n'
        '        return 1\n'
        '    return is_odd(n - 1)\n'
        '\n'
        'fn is_odd(n: int) -> int:\n'
        '    if n == 0:\n'
        '        return 0\n'
        '    return is_even(n - 1)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(is_even(1000000))\n'
        '    print(is_odd(1000001))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1" in out
    # is_even(1M) = 1; is_odd(1000001) = 1
    lines = [l for l in out.splitlines() if l.strip() in ("0", "1")]
    assert lines == ["1", "1"], f"out={out!r}"


def test_mutual_cycle_of_three():
    """f -> g -> h -> f."""
    src = (
        'fn f(n: int) -> int:\n'
        '    if n == 0:\n'
        '        return 100\n'
        '    return g(n - 1)\n'
        '\n'
        'fn g(n: int) -> int:\n'
        '    if n == 0:\n'
        '        return 200\n'
        '    return h(n - 1)\n'
        '\n'
        'fn h(n: int) -> int:\n'
        '    if n == 0:\n'
        '        return 300\n'
        '    return f(n - 1)\n'
        '\n'
        'fn main() -> int:\n'
        '    # 3000 mod 3 == 0 → f(0) → 100\n'
        '    print(f(3000))\n'
        '    # 3001 mod 3 == 1 → f chama g(3000) → g(0) → 200\n'
        '    print(f(3001))\n'
        '    # 3002 mod 3 == 2 → f → g → h(3000) → h(0) → 300\n'
        '    print(f(3002))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l for l in out.splitlines() if l.strip() in ("100", "200", "300")]
    assert lines == ["100", "200", "300"], f"out={out!r}"


def test_mutual_with_extra_param():
    """Múltiplos params — assinaturas idênticas."""
    src = (
        'fn ping(n: int, acc: int) -> int:\n'
        '    if n == 0:\n'
        '        return acc\n'
        '    return pong(n - 1, acc + n)\n'
        '\n'
        'fn pong(n: int, acc: int) -> int:\n'
        '    if n == 0:\n'
        '        return acc\n'
        '    return ping(n - 1, acc + 1)\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = ping(10, 0)\n'
        '    print(r)\n'
        '    return 0\n'
    )
    # Trace:
    #   ping(10, 0)  → acc = 0+10 = 10
    #   pong(9, 10)  → acc = 10+1 = 11
    #   ping(8, 11)  → acc = 11+8 = 19
    #   pong(7, 19)  → acc = 19+1 = 20
    #   ping(6, 20)  → acc = 20+6 = 26
    #   pong(5, 26)  → acc = 26+1 = 27
    #   ping(4, 27)  → acc = 27+4 = 31
    #   pong(3, 31)  → acc = 31+1 = 32
    #   ping(2, 32)  → acc = 32+2 = 34
    #   pong(1, 34)  → acc = 34+1 = 35
    #   ping(0, 35)  → return 35
    out, rc = _run(src)
    assert "35" in out, f"out={out!r}"


# ============================================================
# Regressão: self-recursion continua funcionando
# ============================================================
def test_self_recursion_still_works():
    src = (
        'fn sum_rec(n: int, acc: int) -> int:\n'
        '    if n == 0:\n'
        '        return acc\n'
        '    return sum_rec(n - 1, acc + n)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(sum_rec(1000000, 0))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "500000500000" in out


# ============================================================
# Assinaturas incompatíveis: fallback (sem TCO, ainda funciona)
# ============================================================
def test_incompatible_signatures_fallback():
    """SCC com assinaturas diferentes não vira dispatcher — funciona
    pelo caminho normal, mas sem TCO (recursão pequena aqui)."""
    src = (
        'fn a(n: int) -> int:\n'
        '    if n == 0:\n'
        '        return 0\n'
        '    return b(n)\n'   # retorno de `b` (int) — ok
        '\n'
        'fn b(n: int, extra: int = 0) -> int:\n'
        '    if n == 0:\n'
        '        return 1\n'
        '    return a(n - 1)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(a(3))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # Sem TCO, mas rec N=3 cabe na stack
    assert rc == 0


# ============================================================
# Mutual recursion com defer
# ============================================================
def test_mutual_recursion_emits_defers():
    src = (
        'fn a(n: int) -> int:\n'
        '    defer print("A")\n'
        '    if n == 0:\n'
        '        return 0\n'
        '    return b(n - 1)\n'
        '\n'
        'fn b(n: int) -> int:\n'
        '    defer print("B")\n'
        '    if n == 0:\n'
        '        return 1\n'
        '    return a(n - 1)\n'
        '\n'
        'fn main() -> int:\n'
        '    a(2)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # a(2) → b(1) → a(0). Defers: A (em a0), B (em b1), A (em a2).
    # Total: 2 A, 1 B.
    assert out.count("A") == 2, f"A count, out={out!r}"
    assert out.count("B") == 1, f"B count, out={out!r}"


# ============================================================
# PATCH #8 — Regressão: SCC que chama função genérica
#
# Antes do fix em `lumina/codegen/tco.py`:
#   `_materialize_scc_dispatcher` inicializava
#       self.var_types = {p.type_ann for p in f.params}
#   — um **set** de tipos, não um **dict** {nome: tipo}.
#
#   Quando um membro do SCC chamava uma função genérica, o
#   `_infer_arg_type_lumina` fazia `self.var_types.get(arg_node.name)`
#   e crashava com `AttributeError: 'set' object has no attribute 'get'`.
#
# O bug era silencioso porque nenhum teste de SCC tocava em genéricos.
# Este teste fecha a lacuna.
# ============================================================
def test_scc_member_calls_generic():
    src = (
        'fn ident<T>(x: T) -> T:\n'
        '    return x\n'
        '\n'
        'fn is_even(n: int) -> int:\n'
        '    if n == 0:\n'
        '        return 1\n'
        '    let v = ident(n)\n'
        '    return is_odd(v - 1)\n'
        '\n'
        'fn is_odd(n: int) -> int:\n'
        '    if n == 0:\n'
        '        return 0\n'
        '    return is_even(n - 1)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(is_even(10))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # is_even(10) → is_odd(9) → ... → is_even(0) → 1
    assert rc == 0, f"exit={rc}, out={out!r}"
    assert "1" in out, f"out={out!r}"