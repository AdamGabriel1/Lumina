"""Testes de std/io.

`read_line` usa stdin real — o teste injeta input via pipe.
"""
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _build(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r1 = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        assert r1.returncode == 0, f"Build falhou:\n{r1.stdout}\n{r1.stderr}"
        return path, path[:-3]
    except Exception:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)
        raise


def _run(src, stdin_data="", timeout=30):
    path, binary = _build(src, timeout)
    try:
        r2 = subprocess.run(
            [binary], input=stdin_data,
            capture_output=True, text=True, timeout=timeout,
        )
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def test_write_line():
    src = (
        'import "std/io"\n'
        '\n'
        'fn main() -> int:\n'
        '    write_line("hello")\n'
        '    write_line("world")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "hello" in out
    assert "world" in out


def test_write_no_newline():
    src = (
        'import "std/io"\n'
        '\n'
        'fn main() -> int:\n'
        '    write("a")\n'
        '    write("b")\n'
        '    write_line("")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "ab" in out


def test_read_line():
    src = (
        'import "std/io"\n'
        '\n'
        'fn main() -> int:\n'
        '    let nome = read_line()\n'
        '    write_line(nome)\n'
        '    return 0\n'
    )
    out, rc = _run(src, stdin_data="Adam\n")
    assert "Adam" in out
    # `\n` de stdin foi removido; `write_line` adiciona um só.
    assert out == "Adam\n"


def test_read_int():
    src = (
        'import "std/io"\n'
        '\n'
        'fn main() -> int:\n'
        '    let n = read_int()\n'
        '    let m = read_int()\n'
        '    write_line("sum")\n'
        '    print(n + m)\n'
        '    return 0\n'
    )
    out, rc = _run(src, stdin_data="40\n2\n")
    assert "42" in out


def test_read_line_eof():
    src = (
        'import "std/io"\n'
        '\n'
        'fn main() -> int:\n'
        '    let s = read_line()\n'
        '    if len(s) == 0:\n'
        '        write_line("empty")\n'
        '    return 0\n'
    )
    out, rc = _run(src, stdin_data="")
    assert "empty" in out


def test_eprintln():
    """eprintln escreve em stderr; stdout continua vazio."""
    src = (
        'import "std/io"\n'
        '\n'
        'fn main() -> int:\n'
        '    eprintln("erro!")\n'
        '    return 0\n'
    )
    path, binary = _build(src)
    try:
        r2 = subprocess.run([binary], capture_output=True, text=True, timeout=30)
        assert "erro!" in r2.stderr
        assert "erro!" not in r2.stdout
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)
