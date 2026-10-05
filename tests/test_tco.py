"""Testes de Tail Call Optimization (self-recursion direta).

O codegen detecta `return self(args)` e emite:
  - store dos args nos slots dos params
  - branch de volta para body_bb (sem novo frame)

Sem TCO, `sum_rec(1000000, 0)` estoura a stack.
"""
import os
import pathlib
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


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
        r2 = subprocess.run(
            [binary], capture_output=True, text=True, timeout=timeout,
        )
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def _build_ir(src):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r.returncode == 0, f"Build falhou:\n{r.stdout}\n{r.stderr}"
        with open(path[:-3] + ".ll") as irf:
            return irf.read()
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


# ============================================================
# Comportamento em runtime
# ============================================================
def test_tco_1_million_recursions():
    """Sem TCO, isso estoura stack."""
    src = (
        'fn sum_rec(n: int, acc: int) -> int:\n'
        '    if n == 0:\n'
        '        return acc\n'
        '    return sum_rec(n - 1, acc + n)\n'
        '\n'
        'fn main() -> int:\n'
        '    let res = sum_rec(1000000, 0)\n'
        '    print(res)\n'
        '    return 0\n'
    )
    out, rc = _run(src, timeout=60)
    assert rc == 0
    assert "500000500000" in out, f"Esperado 500000500000, obtido: {out}"


def test_tco_5_million_recursions():
    """5M recursões — só é possível com TCO real."""
    src = (
        'fn sum_rec(n: int, acc: int) -> int:\n'
        '    if n == 0:\n'
        '        return acc\n'
        '    return sum_rec(n - 1, acc + n)\n'
        '\n'
        'fn main() -> int:\n'
        '    let res = sum_rec(5000000, 0)\n'
        '    print(res)\n'
        '    return 0\n'
    )
    out, rc = _run(src, timeout=60)
    assert rc == 0
    # 5M * 5M+1 / 2 = 12_500_002_500_000
    assert "12500002500000" in out


def test_tco_returns_correct_value():
    """Verifica que o loop de TCO preserva a semântica."""
    src = (
        'fn fact(n: int, acc: int) -> int:\n'
        '    if n <= 1:\n'
        '        return acc\n'
        '    return fact(n - 1, acc * n)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(fact(10, 1))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # 10! = 3628800
    assert "3628800" in out


# ============================================================
# Inspeção do IR
# ============================================================
def test_tco_no_call_in_tail_position():
    """O IR da função NÃO deve ter `call i64 @sum_rec` dentro
    dela — senão não é tail call."""
    src = (
        'fn sum_rec(n: int, acc: int) -> int:\n'
        '    if n == 0:\n'
        '        return acc\n'
        '    return sum_rec(n - 1, acc + n)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(sum_rec(100, 0))\n'
        '    return 0\n'
    )
    ir = _build_ir(src)
    norm = " ".join(ir.replace('"', "").split())

    # Acha o corpo de sum_rec (define i64 @sum_rec até a próxima define)
    start = norm.find("define i64 @sum_rec")
    assert start >= 0, f"sum_rec não definida no IR:\n{ir}"
    end = norm.find("define ", start + 1)
    if end < 0:
        end = len(norm)
    body = norm[start:end]

    # Não deve conter chamada recursiva
    assert "call i64 @sum_rec" not in body, (
        f"IR ainda contém `call i64 @sum_rec` — TCO não ativou.\n{body}"
    )
    # E deve ter um bloco body (para onde salta)
    assert "sum_rec_body" in body, (
        f"Falta bloco `sum_rec_body` — TCO não estruturou o IR.\n{body}"
    )


def test_tco_emits_defers_per_iteration():
    """`defer` roda a cada iteração de uma tail call.

    Antes (limitação documentada): defer não rodava em TCO.
    Agora (Sprint 8d): cada iteração encerra o frame virtualmente
    e emite os defers pendentes.
    """
    src = (
        'fn loop(n: int) -> int:\n'
        '    defer print("cleanup")\n'
        '    if n == 0:\n'
        '        return 0\n'
        '    return loop(n - 1)\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = loop(3)\n'
        '    print("done", r)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # Esperado: 3 cleanups (n=3, n=2, n=1), depois "done 0"
    # Nota: n=0 usa `return 0` (não tail call), então emite defer
    # via visit_ReturnStmt normal → 4 iterações contam!
    cleanups = out.count("cleanup")
    assert cleanups == 4, f"cleanup count={cleanups}, out={out!r}"
    assert "done 0" in out


def test_tco_defer_ordering():
    """A ordem dos defers é do mais interno ao mais externo."""
    src = (
        'fn rec(n: int) -> int:\n'
        '    defer print("exit")\n'
        '    if n == 0:\n'
        '        return 0\n'
        '    return rec(n - 1)\n'
        '\n'
        'fn main() -> int:\n'
        '    rec(2)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # 3 "exit" (n=2, n=1, n=0)
    assert out.count("exit") == 3, f"out={out!r}"

# ============================================================
# Defer em TCO
# ============================================================
def test_tco_emits_defers():
    """defer em self-recursion tail-call roda a cada iteração."""
    src = (
        'fn count(n: int) -> int:\n'
        '    defer print("tick")\n'
        '    if n == 0:\n'
        '        return 0\n'
        '    return count(n - 1)\n'
        '\n'
        'fn main() -> int:\n'
        '    count(3)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert out.count("tick") == 4, f"tick count, out={out!r}"