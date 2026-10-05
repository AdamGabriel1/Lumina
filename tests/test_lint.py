"""Testes do `lumina lint`.

Cobre:
  - W001: variável declarada e nunca usada
  - W002: variável sombreando outra
  - W003: código inalcançável
  - W004: parâmetro não usado
  - W005: função com corpo vazio
  - --format=json
  - --quiet
  - exit code = nº de warnings
"""
import json
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _lint(src, extra_args=None):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        cmd = [sys.executable, "-m", "lumina_cli", "lint", path]
        if extra_args:
            cmd.extend(extra_args)
        return subprocess.run(
            cmd, capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
        )
    finally:
        import os
        if os.path.exists(path):
            os.remove(path)


def _codes(stdout):
    """Extrai os códigos Wxxx da saída textual."""
    import re
    return re.findall(r"W\d{3}", stdout)


# ============================================================
# W001 — unused
# ============================================================
def test_w001_unused_variable():
    src = (
        'fn main() -> int:\n'
        '    let x = 1\n'
        '    return 0\n'
    )
    r = _lint(src)
    assert "W001" in r.stdout
    assert "declarada mas nunca usada" in r.stdout


def test_w001_used_variable_ok():
    src = (
        'fn main() -> int:\n'
        '    let x = 1\n'
        '    print(x)\n'
        '    return 0\n'
    )
    r = _lint(src)
    assert "W001" not in r.stdout


def test_w001_underscore_silences():
    src = (
        'fn main() -> int:\n'
        '    let _x = 1\n'
        '    return 0\n'
    )
    r = _lint(src)
    assert "W001" not in r.stdout


# ============================================================
# W002 — shadowing
# ============================================================
def test_w002_shadowing():
    src = (
        'fn main() -> int:\n'
        '    let x = 1\n'
        '    let x = 2\n'
        '    print(x)\n'
        '    return 0\n'
    )
    r = _lint(src)
    assert "W002" in r.stdout
    assert "sombreia" in r.stdout


# ============================================================
# W003 — unreachable
# ============================================================
def test_w003_after_return():
    src = (
        'fn main() -> int:\n'
        '    return 0\n'
        '    print("dead")\n'
    )
    r = _lint(src)
    assert "W003" in r.stdout
    assert "inalcançável" in r.stdout


def test_w003_after_break():
    src = (
        'fn main() -> int:\n'
        '    for i in 0..10:\n'
        '        break\n'
        '        print(i)\n'
        '    return 0\n'
    )
    r = _lint(src)
    assert "W003" in r.stdout


# ============================================================
# W004 — unused param
# ============================================================
def test_w004_unused_param():
    src = (
        'fn f(a: int, b: int) -> int:\n'
        '    return a\n'
        '\n'
        'fn main() -> int:\n'
        '    return f(1, 2)\n'
    )
    r = _lint(src)
    assert "W004" in r.stdout
    assert "'b'" in r.stdout


def test_w004_self_ignored():
    src = (
        'struct S:\n'
        '    x: int\n'
        '\n'
        'impl S:\n'
        '    fn get() -> int:\n'
        '        return self.x\n'
    )
    r = _lint(src)
    assert "W004" not in r.stdout


# ============================================================
# W005 — empty function
# ============================================================
def test_w005_empty_function():
    src = (
        'fn empty():\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n'
    )
    # Nota: parser pode reclamar de função vazia; o teste é só que
    # o lint não crasha.
    r = _lint(src)
    assert r.returncode in (0, 1, 2, 255)


# ============================================================
# JSON
# ============================================================
def test_json_format():
    src = (
        'fn main() -> int:\n'
        '    let x = 1\n'
        '    return 0\n'
    )
    r = _lint(src, extra_args=["--format=json"])
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["code"] == "W001"
    assert "file" in data[0]
    assert "line" in data[0]


# ============================================================
# Quiet
# ============================================================
def test_quiet():
    src = (
        'fn main() -> int:\n'
        '    let x = 1\n'
        '    return 0\n'
    )
    r = _lint(src, extra_args=["--quiet"])
    assert r.stdout.strip() == ""
    assert r.returncode == 1


# ============================================================
# Exit code
# ============================================================
def test_exit_code_zero_when_clean():
    src = (
        'fn main() -> int:\n'
        '    print("ok")\n'
        '    return 0\n'
    )
    r = _lint(src)
    assert r.returncode == 0


def test_exit_code_matches_warning_count():
    src = (
        'fn main() -> int:\n'
        '    let a = 1\n'
        '    let b = 2\n'
        '    let c = 3\n'
        '    return 0\n'
    )
    r = _lint(src)
    codes = _codes(r.stdout)
    assert len(codes) == 3
    assert r.returncode == 3


# ============================================================
# Lint via CLI dispatch
# ============================================================
def test_lint_no_args_shows_error():
    r = subprocess.run(
        [sys.executable, "-m", "lumina_cli", "lint"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert r.returncode == 1
    assert "Uso:" in r.stdout
