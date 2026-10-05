"""Testes de std/path."""
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


def test_basename():
    src = (
        'import "std/path"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(basename("/usr/bin/ls"))\n'
        '    print(basename("foo"))\n'
        '    print(basename("/a/b/c/"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "ls" in out
    assert "foo" in out
    assert "c" in out


def test_dirname():
    src = (
        'import "std/path"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(dirname("/usr/bin/ls"))\n'
        '    print(dirname("foo"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "/usr/bin" in out
    assert "." in out


def test_extension():
    src = (
        'import "std/path"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(extension("foo.txt"))\n'
        '    print(extension("foo"))\n'
        '    print(extension("a.b.c"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert ".txt" in out
    assert ".c" in out


def test_stem():
    src = (
        'import "std/path"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(stem("foo.txt"))\n'
        '    print(stem("foo"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "foo" in out


def test_join():
    src = (
        'import "std/path"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(join("src", "main.lm"))\n'
        '    print(join("src/", "main.lm"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "src/main.lm" in out


def test_is_absolute():
    src = (
        'import "std/path"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(is_absolute("/usr/bin"))\n'
        '    print(is_absolute("foo/bar"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    assert lines == ["1", "0"], f"out={out!r}"


def test_exists(tmp_path):
    """`exists` do caminho atual (`.`) deve ser 1."""
    src = (
        'import "std/path"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(exists("."))\n'
        '    print(exists("/nao_existe_99999"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    assert lines == ["1", "0"], f"out={out!r}"


def test_is_dir():
    src = (
        'import "std/path"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(is_dir("."))\n'
        '    print(is_dir("/etc/hosts"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    assert lines == ["1", "0"], f"out={out!r}"
