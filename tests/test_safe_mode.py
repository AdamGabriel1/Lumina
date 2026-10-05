"""Modo @safe: null check silencioso em MemberExpr/IndexExpr."""
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


def test_safe_member_on_valid_struct():
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        '@safe\n'
        'fn get_id(u: U) -> int:\n'
        '    return u.id\n'
        '\n'
        'fn main() -> int:\n'
        '    mut u: U\n'
        '    u.id = 42\n'
        '    print(get_id(u))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out


def test_safe_member_on_nil_returns_zero():
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        '@safe\n'
        'fn get_id(u: U) -> int:\n'
        '    return u.id\n'
        '\n'
        'fn main() -> int:\n'
        '    let u: U = nil\n'
        '    print(get_id(u))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "0" in out, f"out={out!r}"


def test_unsafe_function_still_fast_path():
    """Sem @safe, u.id com u válido funciona normalmente."""
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn get_id(u: U) -> int:\n'
        '    return u.id\n'
        '\n'
        'fn main() -> int:\n'
        '    mut u: U\n'
        '    u.id = 99\n'
        '    print(get_id(u))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "99" in out


def test_safe_with_safe_nav_still_works():
    """`?.` explícito continua funcionando em @safe."""
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        '@safe\n'
        'fn get_id(u: U) -> int:\n'
        '    return u?.id\n'
        '\n'
        'fn main() -> int:\n'
        '    let u: U = nil\n'
        '    print(get_id(u))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "0" in out


def test_safe_index_on_nil_array():
    src = (
        '@safe\n'
        'fn first(arr: ptr) -> int:\n'
        '    return arr[0]\n'
        '\n'
        'fn main() -> int:\n'
        '    let p: ptr = nil\n'
        '    print(first(p))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "0" in out, f"out={out!r}"


def test_safe_index_on_valid_array():
    src = (
        '@safe\n'
        'fn first(arr: ptr) -> int:\n'
        '    return arr[0]\n'
        '\n'
        'fn main() -> int:\n'
        '    mut arr = alloc(3)\n'
        '    arr[0] = 42\n'
        '    print(first(arr))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out
