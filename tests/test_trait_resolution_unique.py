"""Testes do guard de duplicata em `_resolve_trait_defaults`."""
import os
import subprocess
import sys
import tempfile
import textwrap

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _build(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(textwrap.dedent(src))
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        return r.stdout + r.stderr, r.returncode
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_duplicate_trait_method_detected():
    """Dois traits com mesmo método default no mesmo struct → erro."""
    src = '''
        trait A:
            fn hello() -> int:
                return 1

        trait B:
            fn hello() -> int:
                return 2

        struct S:
            x: int

        impl A for S:
            fn a_only() -> int:
                return 0

        impl B for S:
            fn b_only() -> int:
                return 0
    '''
    out, rc = _build(src)
    assert rc != 0, f"Deveria falhar:\n{out}"
    assert "duplicado" in out.lower(), f"Mensagem esperada:\n{out}"


def test_trait_default_still_works():
    """Sanidade: trait default normal continua funcionando."""
    src = '''
        trait Greeter:
            fn name() -> str
            fn greet() -> int:
                return 42

        struct S:
            x: int

        impl Greeter for S:
            fn name() -> str:
                return "hi"

        fn main() -> int:
            mut s: S
            return s.greet()
    '''
    out, rc = _build(src)
    assert rc == 0, f"Deveria compilar:\n{out}"