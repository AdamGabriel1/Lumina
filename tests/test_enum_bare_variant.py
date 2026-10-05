"""Variantes de enum sem payload podem ser usadas bare.

Ex: `let cmd = Stop` em vez de `let cmd = Stop()`.
Espelha Rust (`None`) e Haskell (`Nothing`).
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
        r2 = subprocess.run(
            [binary], capture_output=True, text=True, timeout=timeout,
        )
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def _lines(out, wanted):
    return [l.strip() for l in out.splitlines() if l.strip() in wanted]


def test_bare_variant_as_value():
    src = (
        'enum Color:\n'
        '    Red\n'
        '    Green\n'
        '    Blue\n'
        '\n'
        'fn name(c: Color) -> str:\n'
        '    match c:\n'
        '        case Red:   return "red"\n'
        '        case Green: return "green"\n'
        '        case Blue:  return "blue"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    let a = Red\n'
        '    let b = Green\n'
        '    print(name(a))\n'
        '    print(name(b))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"red", "green"})
    assert lines == ["red", "green"], f"ordem: {out!r}"


def test_bare_variant_in_function_arg():
    src = (
        'enum State:\n'
        '    On\n'
        '    Off\n'
        '\n'
        'fn describe(s: State) -> str:\n'
        '    match s:\n'
        '        case On:  return "ligado"\n'
        '        case Off: return "desligado"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(describe(On))\n'
        '    print(describe(Off))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"ligado", "desligado"})
    assert lines == ["ligado", "desligado"], f"ordem: {out!r}"


def test_variant_with_payload_still_requires_call():
    """`Some` bare deve ser erro — só `Some(42)` funciona."""
    src = (
        'enum Opt:\n'
        '    Some(int)\n'
        '    None\n'
        '\n'
        'fn main() -> int:\n'
        '    let x = Some\n'
        '    return 0\n'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        # Espera erro: `Some` tem payload, não é variante bare
        assert r.returncode != 0, (
            f"'Some' bare deveria falhar (tem payload):\n{r.stdout}"
        )
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def test_mixed_with_payload_and_nullary():
    src = (
        'enum Cmd:\n'
        '    Start(int)\n'
        '    Stop\n'
        '\n'
        'fn run(c: Cmd) -> str:\n'
        '    match c:\n'
        '        case Start(id): return "start"\n'
        '        case Stop: return "stop"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(run(Start(1)))\n'
        '    print(run(Stop))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"start", "stop"})
    assert lines == ["start", "stop"], f"ordem: {out!r}"
