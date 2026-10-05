"""Testes de regressão para os fixes da Fase 1."""
import os
import subprocess
import sys
import tempfile
import textwrap

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_build(src, timeout=30):
    """Compila `src` (string). Retorna (stdout+stderr, returncode)."""
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


def _run(src, timeout=30):
    """Compila e executa. Retorna (stdout+stderr, returncode)."""
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(textwrap.dedent(src))
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "run", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        return r.stdout + r.stderr, r.returncode
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_safe_mode_preserved_in_generic():
    """Item 1: @safe em função genérica deve gerar null check."""
    src = '''
        struct Box<T>:
            data: T

        struct U:
            id: int

        @safe
        fn get_id<T>(b: Box<T>) -> int:
            return b.data

        fn main() -> int:
            let b: Box<int> = nil
            let r = get_id(b)
            return r
    '''
    out, rc = _run(src)
    assert rc == 0, f"Deve rodar sem SIGSEGV (retorna 0):\n{out}"


def test_inline_noinline_conflict():
    """Item 11: @inline + @noinline deve ser erro."""
    src = '''
        @inline
        @noinline
        fn f() -> int:
            return 1
    '''
    out, rc = _run_build(src)
    assert rc != 0, f"Deveria falhar:\n{out}"
    assert "conflitante" in out, f"Mensagem esperada 'conflitante':\n{out}"


def test_chained_comparison_works():
    """Item 4: a < b < c deve avaliar cada operando 1x."""
    src = '''
        fn side(x: int) -> int:
            print(x)
            return x

        fn main() -> int:
            if side(1) < side(2) < side(3):
                return 0
            return 1
    '''
    out, rc = _run(src)
    assert rc == 0, f"Deve compilar e rodar:\n{out}"
    # Conta linhas cujo conteúdo é exatamente "1", "2" ou "3" — evita
    # contar "1." de "1. Análise Léxica" da saída do CLI.
    lines = [l.strip() for l in out.splitlines()]
    assert lines.count("1") == 1, f"side(1) chamado != 1x:\n{out}"
    assert lines.count("2") == 1, f"side(2) chamado != 1x:\n{out}"
    assert lines.count("3") == 1, f"side(3) chamado != 1x:\n{out}"


def test_alloc_zero_rejected():
    """Extra: alloc(0) deve ser erro."""
    src = '''
        fn main() -> int:
            let x = alloc(0)
            return 0
    '''
    out, rc = _run_build(src)
    assert rc != 0, f"Deveria falhar:\n{out}"
    assert "positivo" in out or "inválido" in out, f"Mensagem esperada:\n{out}"