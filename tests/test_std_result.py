"""Testes de `std/result.lm` — helpers sobre `Result`.

Cobre:
  - is_ok / is_err
  - unwrap / unwrap_or
  - expect
  - map / and_then
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
# is_ok / is_err
# ============================================================
def test_is_ok_true():
    src = (
        'import "std/result"\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = Ok(5)\n'
        '    print(is_ok(r))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1" in out


def test_is_ok_false():
    src = (
        'import "std/result"\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = Err(1)\n'
        '    print(is_ok(r))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "0" in out


def test_is_err():
    src = (
        'import "std/result"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(is_err(Ok(1)))\n'
        '    print(is_err(Err(1)))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert _lines(out, {"0", "1"}) == ["0", "1"]


# ============================================================
# unwrap / unwrap_or
# ============================================================
def test_unwrap_ok():
    src = (
        'import "std/result"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(unwrap(Ok(42)))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out


def test_unwrap_or():
    src = (
        'import "std/result"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(unwrap_or(Ok(1), 99))\n'
        '    print(unwrap_or(Err(0), 99))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert _lines(out, {"1", "99"}) == ["1", "99"]


# ============================================================
# map
# ============================================================
def test_map_ok():
    src = (
        'import "std/result"\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = Ok(5)\n'
        '    let doubled = map(r, fn(x: int) -> int: x * 2)\n'
        '    print(unwrap(doubled))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "10" in out


def test_map_err_passes_through():
    src = (
        'import "std/result"\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = Err(7)\n'
        '    let mapped = map(r, fn(x: int) -> int: x * 2)\n'
        '    print(is_err(mapped))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1" in out


# ============================================================
# is_ok_and
# ============================================================
def test_is_ok_and():
    src = (
        'import "std/result"\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = Ok(10)\n'
        '    print(is_ok_and(r, fn(x: int) -> int: x > 5))\n'
        '    print(is_ok_and(r, fn(x: int) -> int: x > 20))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert _lines(out, {"0", "1"}) == ["1", "0"]


# ============================================================
# Integração
# ============================================================
def test_divide_and_unwrap():
    src = (
        'import "std/result"\n'
        '\n'
        'fn divide(a: int, b: int) -> Result:\n'
        '    if b == 0:\n'
        '        return Err(1)\n'
        '    return Ok(a / b)\n'
        '\n'
        'fn main() -> int:\n'
        '    let r1 = divide(10, 2)\n'
        '    let r2 = divide(10, 0)\n'
        '    print(unwrap(r1))\n'
        '    print(unwrap_or(r2, -1))\n'
        '    print(is_ok(r1), is_err(r2))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "5" in out
    assert "-1" in out
    assert "1 1" in out
