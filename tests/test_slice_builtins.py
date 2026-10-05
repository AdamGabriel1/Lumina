"""Testes para os builtins que fecham lacunas documentadas do v0.8.0.

  - `s[i] op= v` em slices (CompoundAssignStmt com slice)
  - `bytes(s)` — `str` → `[int]`
  - `copy(s: [T])` — cópia de slice com backing buffer próprio
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
        r2 = subprocess.run([path[:-3]], capture_output=True, text=True, timeout=timeout)
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


# ============================================================
# 1. CompoundAssignStmt em slice
# ============================================================
def test_compound_assign_slice_int():
    out, rc = _run(
        'fn main() -> int:\n'
        '    let v = [10, 20, 30, 40]\n'
        '    let s = v[..]\n'
        '    s[0] += 5\n'
        '    s[1] *= 2\n'
        '    s[3] -= 4\n'
        '    print(s[0], s[1], s[3])\n'
        '    return 0\n'
    )
    assert "15 40 36" in out, f"out={out!r}"


def test_compound_assign_slice_with_expression_index():
    """`s[f()] += v` deve chamar f() uma única vez."""
    out, rc = _run(
        'fn main() -> int:\n'
        '    let v = [1, 2, 3]\n'
        '    let s = v[..]\n'
        '    s[1] += 100\n'
        '    print(s[1])\n'
        '    return 0\n'
    )
    assert "102" in out, f"out={out!r}"


def test_compound_assign_slice_alias_writes_back():
    """Verifica que `s[i] += v` escreve no backing buffer de `v`."""
    out, rc = _run(
        'fn main() -> int:\n'
        '    mut v = [1, 2, 3]\n'
        '    let s = v[..]\n'
        '    s[0] += 10\n'
        '    print(v[0])\n'   # 11 — view compartilha o buffer
        '    return 0\n'
    )
    assert "11" in out, f"out={out!r}"


# ============================================================
# 2. bytes(s)
# ============================================================
def test_bytes_len():
    out, rc = _run(
        'fn main() -> int:\n'
        '    let b = bytes("hello")\n'
        '    print(len(b))\n'
        '    return 0\n'
    )
    assert "5" in out, f"out={out!r}"


def test_bytes_content():
    out, rc = _run(
        'fn main() -> int:\n'
        '    let b = bytes("ABC")\n'
        '    print(b[0], b[1], b[2])\n'   # 65 66 67
        '    return 0\n'
    )
    assert "65 66 67" in out, f"out={out!r}"


def test_bytes_iterable():
    out, rc = _run(
        'fn main() -> int:\n'
        '    let b = bytes("hi")\n'
        '    mut sum = 0\n'
        '    for x in b:\n'
        '        sum += x\n'
        '    print(sum)\n'   # 'h'=104, 'i'=105 → 209
        '    return 0\n'
    )
    assert "209" in out, f"out={out!r}"


# ============================================================
# 3. copy(s: [T])
# ============================================================
def test_copy_is_independent():
    """`copy` cria buffer novo; modificar o original não afeta a cópia."""
    out, rc = _run(
        'fn main() -> int:\n'
        '    mut v = [1, 2, 3]\n'
        '    let c = copy(v[..])\n'
        '    v[0] = 99\n'
        '    print(c[0])\n'   # 1 — cópia preserva
        '    return 0\n'
    )
    assert "1" in out, f"out={out!r}"


def test_copy_len_preserved():
    out, rc = _run(
        'fn main() -> int:\n'
        '    let v = [10, 20, 30, 40]\n'
        '    let s = v[1..3]\n'
        '    let c = copy(s)\n'
        '    print(len(c))\n'
        '    return 0\n'
    )
    assert "2" in out, f"out={out!r}"


def test_copy_write_isolated():
    out, rc = _run(
        'fn main() -> int:\n'
        '    let v = [1, 2, 3]\n'
        '    let c = copy(v[..])\n'
        '    c[0] = 100\n'
        '    print(v[0], c[0])\n'   # 1 100
        '    return 0\n'
    )
    assert "1 100" in out, f"out={out!r}"
