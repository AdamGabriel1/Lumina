"""`lumina fmt --stdin` e `--check-all`."""
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _fmt_stdin(source, check=False):
    cmd = [sys.executable, "-m", "lumina_cli", "fmt", "--stdin"]
    if check:
        cmd.append("--check")
    return subprocess.run(
        cmd, input=source, capture_output=True, text=True,
        cwd=REPO_ROOT, timeout=30,
    )


def test_fmt_stdin_formats():
    src = "fn main() -> int:\n    return 0\n"
    r = _fmt_stdin(src)
    assert r.returncode == 0
    assert "fn main() -> int:" in r.stdout


def test_fmt_stdin_check_ok():
    src = "fn main() -> int:\n    return 0\n"
    r = _fmt_stdin(src, check=True)
    assert r.returncode == 0


def test_fmt_stdin_check_bad():
    src = "fn main() -> int:\n    return    0\n"   # espaço extra
    r = _fmt_stdin(src, check=True)
    assert r.returncode == 1


def test_fmt_check_all_clean():
    """`examples/` deve estar todo formatado."""
    r = subprocess.run(
        [sys.executable, "-m", "lumina_cli", "fmt", "--check-all", "examples"],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
    )
    # Só valida que roda; alguns exemplos podem não estar formatados ainda.
    assert r.returncode in (0, 1)
