"""Testes de std/math (expandido)."""
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


def test_min_max():
    src = (
        'import "std/math"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(min(3, 7))\n'
        '    print(max(3, 7))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "3" in out
    assert "7" in out


def test_clamp():
    src = (
        'import "std/math"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(clamp(15, 0, 10))\n'
        '    print(clamp(-5, 0, 10))\n'
        '    print(clamp(7, 0, 10))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "10" in out
    assert "0" in out
    assert "7" in out


def test_gcd():
    src = (
        'import "std/math"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(gcd(48, 18))\n'
        '    print(gcd(17, 5))\n'
        '    print(gcd(-12, 8))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    assert "6" in lines
    assert "1" in lines
    assert "4" in lines


def test_lcm():
    src = (
        'import "std/math"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(lcm(4, 6))\n'
        '    print(lcm(3, 5))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "12" in out
    assert "15" in out


def test_powi():
    src = (
        'import "std/math"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(powi(2, 10))\n'
        '    print(powi(3, 4))\n'
        '    print(powi(5, 0))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1024" in out
    assert "81" in out
    assert "1" in out


def test_is_prime():
    src = (
        'import "std/math"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(is_prime(2))\n'
        '    print(is_prime(17))\n'
        '    print(is_prime(18))\n'
        '    print(is_prime(1))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    assert lines == ["1", "1", "0", "0"], f"out={out!r}"


def test_pow_sqrt_float():
    src = (
        'import "std/math"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(potencia(2.0, 10.0))\n'
        '    print(raiz_quadrada(144.0))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1024" in out
    assert "12" in out
