"""Null real para structs via `nil`.

Antes: só dava para representar "opcional" com `none` (Option::None).
Agora `nil` produz null pointer C-style, compatível com ptr/str/fn/struct.
`u?.campo` faz null check e devolve 0 quando u é nil.
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


# ============================================================
# Declaração com nil
# ============================================================
def test_declare_struct_nil():
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let u: U = nil\n'
        '    print("ok")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "ok" in out


def test_struct_not_nil_works():
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut u: U\n'
        '    u.id = 42\n'
        '    print(u.id)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out


# ============================================================
# Comparação com nil
# ============================================================
def test_compare_nil_true():
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let u: U = nil\n'
        '    if u == nil:\n'
        '        print("é nil")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "é nil" in out


def test_compare_nil_false():
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut u: U\n'
        '    u.id = 1\n'
        '    if u == nil:\n'
        '        print("nil")\n'
        '    else:\n'
        '        print("não nil")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "não nil" in out


# ============================================================
# Safe nav em nil
# ============================================================
def test_safe_nav_on_nil_returns_zero():
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let u: U = nil\n'
        '    let v = u?.id\n'
        '    print(v)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "0" in out


def test_safe_nav_on_valid_returns_value():
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut u: U\n'
        '    u.id = 99\n'
        '    let v = u?.id\n'
        '    print(v)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "99" in out


# ============================================================
# Atribuição
# ============================================================
def test_assign_nil_to_mut():
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut u: U\n'
        '    u.id = 5\n'
        '    u = nil\n'
        '    if u == nil:\n'
        '        print("agora é nil")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "agora é nil" in out


# ============================================================
# nil como parâmetro
# ============================================================
def test_nil_as_function_arg():
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn check(u: U) -> int:\n'
        '    if u == nil:\n'
        '        return -1\n'
        '    return u.id\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = check(nil)\n'
        '    print(r)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "-1" in out


# ============================================================
# Regressão: `none` continua funcionando (Option)
# ============================================================
def test_none_still_works():
    src = (
        'fn main() -> int:\n'
        '    let x: Option = none\n'
        '    match x:\n'
        '        case Some(v): print("some")\n'
        '        case None:    print("none")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "none" in out


# ============================================================
# Nil em let sem anotação (default ptr)
# ============================================================
def test_nil_without_annotation():
    src = (
        'fn main() -> int:\n'
        '    let x = nil\n'
        '    print("declarou")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "declarou" in out
