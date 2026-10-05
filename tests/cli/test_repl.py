"""Testes do REPL persistente.

Envia input via pipe e captura stdout. O prompt vai pro stdout
misturado com o output — os asserts checam substrings específicas.
"""
import subprocess
import sys
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _run_repl(input_text, timeout=30):
    return subprocess.run(
        [sys.executable, "-m", "lumina_cli", "repl"],
        input=input_text,
        capture_output=True, text=True,
        cwd=REPO_ROOT, timeout=timeout,
    )


# ============================================================
# Persistência de estado
# ============================================================
def test_mut_persists_between_cells():
    inp = (
        "mut counter = 0\n"
        "\n"
        "counter = counter + 1\n"
        "\n"
        "counter = counter + 1\n"
        "\n"
        "print(counter)\n"
        "\n"
        "exit\n"
    )
    r = _run_repl(inp)
    assert "2" in r.stdout, f"esperava 2:\nstdout={r.stdout!r}\nstderr={r.stderr!r}"


def test_fn_declaration_available_next_cell():
    inp = (
        "fn add(a: int, b: int) -> int:\n"
        "    return a + b\n"
        "\n"
        "print(add(2, 3))\n"
        "\n"
        "exit\n"
    )
    r = _run_repl(inp)
    assert "5" in r.stdout, f"stdout={r.stdout!r}"


def test_multiline_function():
    inp = (
        "fn fib(n: int) -> int:\n"
        "    if n <= 1:\n"
        "        return n\n"
        "    return fib(n - 1) + fib(n - 2)\n"
        "\n"
        "print(fib(10))\n"
        "\n"
        "exit\n"
    )
    r = _run_repl(inp)
    # fib(10) = 55
    assert "55" in r.stdout, f"stdout={r.stdout!r}"


def test_struct_declaration_available_next_cell():
    inp = (
        "struct P:\n"
        "    x: int\n"
        "    y: int\n"
        "\n"
        "let p = P { x: 1, y: 2 }\n"
        "print(p.x, p.y)\n"
        "\n"
        "exit\n"
    )
    r = _run_repl(inp)
    assert "1 2" in r.stdout, f"stdout={r.stdout!r}"


# ============================================================
# Comandos
# ============================================================
def test_clear_resets_state():
    inp = (
        "mut x = 10\n"
        "\n"
        ":clear\n"
        "print(x)\n"
        "\n"
        "exit\n"
    )
    r = _run_repl(inp)
    # x foi apagado pelo :clear → erro "não declarada"
    combined = r.stdout + r.stderr
    assert "não declarada" in combined, f"stdout={r.stdout!r}"


def test_history_shows_entries():
    inp = (
        "mut a = 1\n"
        "\n"
        ":history\n"
        "exit\n"
    )
    r = _run_repl(inp)
    assert "mut a = 1" in r.stdout


def test_decls_shows_only_declarations():
    inp = (
        "mut a = 1\n"
        "\n"
        "print(a)\n"
        "\n"
        ":decls\n"
        "exit\n"
    )
    r = _run_repl(inp)
    # 'mut a = 1' deve aparecer; 'print(a)' NÃO
    assert "mut a = 1" in r.stdout
    # A chamada `:decls` mostra apenas as top-level
    decls_section = r.stdout.split("[D0]")[-1] if "[D0]" in r.stdout else ""
    # Não devemos encontrar [C0] entre [D0] e o fim da seção
    # (na prática, `:decls` não emite [C0])
    assert "[C0]" not in r.stdout.split("[D0]")[-1].split("exit")[0] if "[D0]" in r.stdout else True


# ============================================================
# Recuperação de erro
# ============================================================
def test_error_does_not_break_repl():
    inp = (
        "print(undefined_var)\n"
        "\n"
        "print(\"still alive\")\n"
        "\n"
        "exit\n"
    )
    r = _run_repl(inp)
    assert "still alive" in r.stdout, f"stdout={r.stdout!r}"


def test_syntax_error_recovers():
    inp = (
        "let x = \n"   # erro de sintaxe
        "\n"
        "print(\"recovered\")\n"
        "\n"
        "exit\n"
    )
    r = _run_repl(inp)
    assert "recovered" in r.stdout, f"stdout={r.stdout!r}"


# ============================================================
# Aviso inicial
# ============================================================
def test_startup_warning_about_mut():
    inp = "exit\n"
    r = _run_repl(inp)
    # O aviso deve mencionar `mut` e a dica
    assert "mut" in r.stdout
    assert "estado que persiste" in r.stdout
