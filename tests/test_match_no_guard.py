"""Regressão: match sem guard continua funcionando após o refactor.

O `_codegen_match_int` original usava `switch` (jump table). O
refactor substituiu por chain sequencial de `icmp eq`. Estes testes
garantem que a semântica (caso casado, fallthrough para default)
está preservada.
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


# ============================================================
# Match int sem guard
# ============================================================
def test_int_match_multiple_cases():
    src = (
        'fn label(n: int) -> str:\n'
        '    match n:\n'
        '        case 1: return "um"\n'
        '        case 2: return "dois"\n'
        '        case 3: return "três"\n'
        '        default: return "outro"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(label(1))\n'
        '    print(label(2))\n'
        '    print(label(3))\n'
        '    print(label(99))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"um", "dois", "três", "outro"})
    assert lines == ["um", "dois", "três", "outro"], f"ordem: {out!r}"


def test_int_match_no_default_falls_through():
    src = (
        'fn maybe(n: int) -> int:\n'
        '    match n:\n'
        '        case 1: return 10\n'
        '        case 2: return 20\n'
        '    return -1\n'
        '\n'
        'fn main() -> int:\n'
        '    print(maybe(1))\n'
        '    print(maybe(2))\n'
        '    print(maybe(99))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"10", "20", "-1"})
    assert lines == ["10", "20", "-1"], f"ordem: {out!r}"


def test_switch_syntax_still_works():
    """`switch` (que é o mesmo que match no parser) funciona."""
    src = (
        'fn label(n: int) -> str:\n'
        '    switch n:\n'
        '        case 1: return "a"\n'
        '        case 2: return "b"\n'
        '        default: return "?"\n'
        '    return "!"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(label(1))\n'
        '    print(label(2))\n'
        '    print(label(3))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"a", "b", "?"})
    assert lines == ["a", "b", "?"], f"ordem: {out!r}"


# ============================================================
# Match enum sem guard
# ============================================================
def test_enum_match_no_guard():
    src = (
        'enum Cmd:\n'
        '    Start(int)\n'
        '    Stop\n'
        '\n'
        'fn run(c: Cmd) -> str:\n'
        '    match c:\n'
        '        case Start(id):\n'
        '            return "start"\n'
        '        case Stop:\n'
        '            return "stop"\n'
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


# ============================================================
# Match str sem guard
# ============================================================
def test_str_match_no_guard():
    src = (
        'fn route(cmd: str) -> str:\n'
        '    match cmd:\n'
        '        case "get": return "GET"\n'
        '        case "post": return "POST"\n'
        '        default: return "?"\n'
        '    return "!"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(route("get"))\n'
        '    print(route("post"))\n'
        '    print(route("delete"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"GET", "POST", "?"})
    assert lines == ["GET", "POST", "?"], f"ordem: {out!r}"


# ============================================================
# Match com todos os tipos + guard (integração)
# ============================================================
def test_all_kinds_still_work_together():
    src = (
        'enum E:\n'
        '    A(int)\n'
        '    B\n'
        '\n'
        'fn f_int(n: int) -> str:\n'
        '    match n:\n'
        '        case x if x > 100: return "grande"\n'
        '        case x: return "pequeno"\n'
        '    return "?"\n'
        '\n'
        'fn f_enum(e: E) -> str:\n'
        '    match e:\n'
        '        case A(v) if v > 10: return "A-grande"\n'
        '        case A(v): return "A-pequeno"\n'
        '        case B: return "B"\n'
        '    return "?"\n'
        '\n'
        'fn f_str(s: str) -> str:\n'
        '    match s:\n'
        '        case x if x.starts_with("hi"): return "saudação"\n'
        '        case x: return "outro"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(f_int(200))\n'
        '    print(f_int(5))\n'
        '    print(f_enum(A(20)))\n'
        '    print(f_enum(A(2)))\n'
        '    print(f_enum(B))\n'
        '    print(f_str("hi there"))\n'
        '    print(f_str("bye"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    wanted = {"grande", "pequeno", "A-grande", "A-pequeno", "B",
              "saudação", "outro"}
    lines = _lines(out, wanted)
    assert lines == [
        "grande", "pequeno",
        "A-grande", "A-pequeno", "B",
        "saudação", "outro",
    ], f"ordem: {out!r}"
