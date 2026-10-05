"""Multi-pattern (`case 1 | 2:`) e wildcard `case _:`.

5b: alternativa `|` no pattern. Aceita literais (int, str) e
    variantes nullary. Bindings + multi-pattern é rejeitado.

5c: `_` é wildcard que casa sem binding, equivalente a `default:`
    mas pode aparecer em qualquer posição.
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


def _lines(out, wanted):
    return [l.strip() for l in out.splitlines() if l.strip() in wanted]


# ============================================================
# 5b — Multi-pattern em int
# ============================================================
def test_multi_pattern_int():
    src = (
        'fn classify(n: int) -> str:\n'
        '    match n:\n'
        '        case 1 | 2 | 3: return "pequeno"\n'
        '        case 4 | 5:     return "medio"\n'
        '        default:        return "grande"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(classify(1))\n'
        '    print(classify(3))\n'
        '    print(classify(5))\n'
        '    print(classify(99))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"pequeno", "medio", "grande"})
    assert lines == ["pequeno", "pequeno", "medio", "grande"], f"ordem: {out!r}"


def test_multi_pattern_str():
    src = (
        'fn idempotent(method: str) -> int:\n'
        '    match method:\n'
        '        case "GET" | "HEAD": return 1\n'
        '        case "POST" | "PUT": return 0\n'
        '        default: return -1\n'
        '    return -2\n'
        '\n'
        'fn main() -> int:\n'
        '    print(idempotent("GET"))\n'
        '    print(idempotent("HEAD"))\n'
        '    print(idempotent("POST"))\n'
        '    print(idempotent("DELETE"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"1", "0", "-1"})
    assert lines == ["1", "1", "0", "-1"], f"ordem: {out!r}"


def test_multi_pattern_enum_nullary():
    src = (
        'enum Color:\n'
        '    Red\n'
        '    Green\n'
        '    Blue\n'
        '\n'
        'fn warm(c: Color) -> str:\n'
        '    match c:\n'
        '        case Red: return "warm"\n'
        '        case Green | Blue: return "cool"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(warm(Red))\n'
        '    print(warm(Green))\n'
        '    print(warm(Blue))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"warm", "cool"})
    assert lines == ["warm", "cool", "cool"], f"ordem: {out!r}"


def test_multi_pattern_with_guard():
    src = (
        'fn f(n: int, big: int) -> str:\n'
        '    match n:\n'
        '        case 1 | 2 if big == 1: return "pequeno-e-grande"\n'
        '        case 1 | 2: return "pequeno"\n'
        '        default: return "outro"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(f(1, 1))\n'
        '    print(f(2, 0))\n'
        '    print(f(3, 1))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"pequeno-e-grande", "pequeno", "outro"})
    assert lines == ["pequeno-e-grande", "pequeno", "outro"], f"ordem: {out!r}"


def test_multi_pattern_with_binding_rejected():
    src = (
        'enum E:\n'
        '    A(int)\n'
        '    B(int)\n'
        '\n'
        'fn f(e: E) -> int:\n'
        '    match e:\n'
        '        case A(x) | B(x): return x\n'
        '    return 0\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n'
    )
    r = _build(src)
    assert r.returncode != 0, "binding + multi-pattern deveria falhar"
    assert "Multi-pattern com binding" in r.stdout


# ============================================================
# 5c — Wildcard `_`
# ============================================================
def test_wildcard_basic():
    src = (
        'fn label(n: int) -> str:\n'
        '    match n:\n'
        '        case 1: return "um"\n'
        '        case _: return "outro"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(label(1))\n'
        '    print(label(99))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"um", "outro"})
    assert lines == ["um", "outro"], f"ordem: {out!r}"


def test_wildcard_does_not_bind():
    """`_` não cria variável visível no corpo."""
    src = (
        'fn f(n: int) -> int:\n'
        '    match n:\n'
        '        case 1: return 10\n'
        '        case _: return 20\n'
        '    return 0\n'
        '\n'
        'fn main() -> int:\n'
        '    print(f(5))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "20" in out


def test_wildcard_in_str_match():
    src = (
        'fn route(cmd: str) -> str:\n'
        '    match cmd:\n'
        '        case "get": return "GET"\n'
        '        case _: return "other"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(route("get"))\n'
        '    print(route("put"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"GET", "other"})
    assert lines == ["GET", "other"], f"ordem: {out!r}"
