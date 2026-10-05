"""Testes de runtime que expõem bugs silenciosos no codegen.

Diferente de test_codegen_bugs.py (que inspeciona o IR), estes
COMPILAM E EXECUTAM o binário, então pegam regressões reais.
"""
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(src, timeout=15):
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


# ============================================================
# break / continue
# ============================================================
def test_break_exits_loop():
    src = (
        'fn main() -> int:\n'
        '    mut count = 0\n'
        '    for i in 0..100:\n'
        '        if i == 5:\n'
        '            break\n'
        '        count += 1\n'
        '    print(count)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "5" in out and "100" not in out.split()[0], f"break no-op: {out!r}"


def test_continue_skips():
    src = (
        'fn main() -> int:\n'
        '    mut s = 0\n'
        '    for i in 0..5:\n'
        '        if i == 2:\n'
        '            continue\n'
        '        s += i\n'
        '    print(s)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "8" in out, f"continue no-op (esperado 8): {out!r}"


# ============================================================
# assert
# ============================================================
def test_assert_true_continues():
    src = (
        'fn main() -> int:\n'
        '    assert(1 == 1)\n'
        '    print("ok")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "ok" in out
    assert rc == 0


def test_assert_false_aborts():
    src = (
        'fn main() -> int:\n'
        '    print("antes")\n'
        '    assert(1 == 2)\n'
        '    print("depois")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "antes" in out
    assert "depois" not in out, f"assert não abortou: {out!r}"
    assert rc != 0, f"exit code deveria ser != 0, veio {rc}"


# ============================================================
# defer
# ============================================================
def test_defer_runs_at_function_end():
    src = (
        'fn main() -> int:\n'
        '    print("a")\n'
        '    defer print("b")\n'
        '    print("c")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l for l in out.strip().split("\n") if l in ("a", "b", "c")]
    assert lines == ["a", "c", "b"], f"defer executou inline: {out!r}"


def test_defer_runs_before_early_return():
    src = (
        'fn main() -> int:\n'
        '    defer print("defer")\n'
        '    print("antes do return")\n'
        '    return 42\n'
    )
    out, rc = _run(src)
    lines = [l for l in out.strip().split("\n") if l in ("antes do return", "defer")]
    assert lines == ["antes do return", "defer"], f"ordem errada: {out!r}"
    assert rc == 42


# ============================================================
# short-circuit
# ============================================================
def test_and_short_circuits():
    src = (
        'fn main() -> int:\n'
        '    let x = 0\n'
        '    if x != 0 and 10 / x > 1:\n'
        '        print("nunca")\n'
        '    print("ok")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "ok" in out, f"short-circuit falhou: {out!r}"


def test_or_short_circuits():
    src = (
        'fn main() -> int:\n'
        '    let x = 0\n'
        '    if x == 0 or 10 / x > 1:\n'
        '        print("primeiro")\n'
        '    print("fim")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "primeiro" in out and "fim" in out, f"or short-circuit: {out!r}"


# ============================================================
# formatter preserva @attrs
# ============================================================
def test_fmt_preserves_derive():
    src = (
        '@derive(Eq, Debug)\n'
        'struct Ponto:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "fmt", path],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r.returncode == 0
        with open(path) as f:
            result = f.read()
        assert "@derive(Eq, Debug)" in result, f"formatter apagou @attrs:\n{result}"
    finally:
        os.remove(path)
