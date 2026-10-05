"""Suporte a `if cond: stmt` inline (v1.0.x).

Cobre:
  - if inline com return
  - if inline com print
  - if inline com assignment
  - if inline dentro de bloco indentado
  - if multi-linha continua funcionando
  - elif/else inline
  - ausência de ambiguidade com comentário trailing
"""
import os, pathlib, subprocess, sys, tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src); path = f.name
    try:
        r1 = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        assert r1.returncode == 0, f"Build falhou:\n{r1.stdout}\n{r1.stderr}"
        r2 = subprocess.run([path[:-3]], capture_output=True, text=True, timeout=timeout)
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def test_if_inline_return():
    out, _ = _run(
        'fn f(x: int) -> int:\n'
        '    if x > 0: return 1\n'
        '    return 0\n'
        '\n'
        'fn main() -> int:\n'
        '    print(f(5))\n'
        '    print(f(-1))\n'
        '    return 0\n'
    )
    lines = [l.strip() for l in out.splitlines() if l.strip() in ("0", "1")]
    assert lines == ["1", "0"], f"out={out!r}"


def test_if_inline_print():
    out, _ = _run(
        'fn main() -> int:\n'
        '    if 1 == 1: print("yes")\n'
        '    if 1 == 2: print("no")\n'
        '    return 0\n'
    )
    assert "yes" in out
    assert "no" not in out


def test_if_inline_assignment():
    out, _ = _run(
        'fn main() -> int:\n'
        '    mut x = 0\n'
        '    if 1 == 1: x = 42\n'
        '    print(x)\n'
        '    return 0\n'
    )
    assert "42" in out


def test_if_inline_inside_indented_block():
    """`if ...: return` dentro de um corpo indentado."""
    out, _ = _run(
        'fn f(x: int) -> int:\n'
        '    while 1 == 1:\n'
        '        if x > 0: return 100\n'
        '        return 0\n'
        '    return -1\n'
        '\n'
        'fn main() -> int:\n'
        '    print(f(5))\n'
        '    return 0\n'
    )
    assert "100" in out


def test_if_multiline_still_works():
    """Forma multi-linha não regride."""
    out, _ = _run(
        'fn main() -> int:\n'
        '    if 1 == 1:\n'
        '        print("multi")\n'
        '    return 0\n'
    )
    assert "multi" in out


def test_else_inline():
    out, _ = _run(
        'fn f(x: int) -> int:\n'
        '    if x > 0: return 1\n'
        '    else: return -1\n'
        '\n'
        'fn main() -> int:\n'
        '    print(f(5))\n'
        '    print(f(-5))\n'
        '    return 0\n'
    )
    lines = [l.strip() for l in out.splitlines() if l.strip() in ("1", "-1")]
    assert lines == ["1", "-1"], f"out={out!r}"


def test_if_inline_with_trailing_comment():
    """Comentário trailing depois do `:` é ignorado corretamente."""
    out, _ = _run(
        'fn main() -> int:\n'
        '    if 1 == 1:  # comment\n'
        '        print("multi")\n'
        '    return 0\n'
    )
    assert "multi" in out
