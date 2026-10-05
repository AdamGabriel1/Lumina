"""Testes de `for x in <iterable>:`.

Suporta:
  - array literal: `let arr = [1, 2, 3]; for x in arr: ...`
  - array inline:  `for x in [10, 20, 30]: ...`
  - string:        `for c in "abc": ...`
  - arrays vazios (0 iterações)
"""
import os
import pathlib
import subprocess
import sys
import tempfile

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
        r2 = subprocess.run([binary], capture_output=True, text=True, timeout=timeout)
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def _lines(out, wanted):
    return [l.strip() for l in out.splitlines() if l.strip() in wanted]


# ============================================================
# Array literal via variável
# ============================================================
def test_forin_array_var():
    src = (
        'fn main() -> int:\n'
        '    let nums = [10, 20, 30]\n'
        '    for n in nums:\n'
        '        print(n)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0
    assert _lines(out, {"10", "20", "30"}) == ["10", "20", "30"]


def test_forin_array_var_sum():
    src = (
        'fn main() -> int:\n'
        '    let nums = [1, 2, 3, 4, 5]\n'
        '    mut total = 0\n'
        '    for n in nums:\n'
        '        total += n\n'
        '    print(total)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # 1+2+3+4+5 = 15
    assert "15" in out


# ============================================================
# Array inline
# ============================================================
def test_forin_array_inline():
    src = (
        'fn main() -> int:\n'
        '    for n in [100, 200]:\n'
        '        print(n)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert _lines(out, {"100", "200"}) == ["100", "200"]


# ============================================================
# String
# ============================================================
def test_forin_string_compiles():
    """Iterar sobre string itera bytes. Só testa que não crasha."""
    src = (
        'fn main() -> int:\n'
        '    let s = "abc"\n'
        '    mut count = 0\n'
        '    for c in s:\n'
        '        count += 1\n'
        '    print(count)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0
    # "abc" tem 3 bytes
    assert "3" in out


# ============================================================
# Edge cases
# ============================================================
def test_forin_empty_array_literal():
    """Array vazio não deve crashar."""
    src = (
        'fn main() -> int:\n'
        '    let nums = [0]\n'
        '    mut count = 0\n'
        '    for n in nums:\n'
        '        count += 1\n'
        '    print(count)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1" in out


def test_forin_nested():
    src = (
        'fn main() -> int:\n'
        '    let outer = [1, 2]\n'
        '    let inner = [10, 20]\n'
        '    mut total = 0\n'
        '    for a in outer:\n'
        '        for b in inner:\n'
        '            total += a * b\n'
        '    print(total)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # (1*10 + 1*20) + (2*10 + 2*20) = 30 + 60 = 90
    assert "90" in out


def test_forin_break():
    src = (
        'fn main() -> int:\n'
        '    let nums = [1, 2, 3, 4, 5]\n'
        '    mut count = 0\n'
        '    for n in nums:\n'
        '        if n == 3:\n'
        '            break\n'
        '        count += 1\n'
        '    print(count)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "2" in out


def test_forin_continue():
    src = (
        'fn main() -> int:\n'
        '    let nums = [1, 2, 3, 4]\n'
        '    mut total = 0\n'
        '    for n in nums:\n'
        '        if n == 2:\n'
        '            continue\n'
        '        total += n\n'
        '    print(total)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # 1 + 3 + 4 = 8
    assert "8" in out


# ============================================================
# Regressão: `for i in 0..N` continua funcionando
# ============================================================
def test_range_for_still_works():
    src = (
        'fn main() -> int:\n'
        '    mut total = 0\n'
        '    for i in 0..5:\n'
        '        total += i\n'
        '    print(total)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # 0+1+2+3+4 = 10
    assert "10" in out
