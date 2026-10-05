"""Verifica que exit codes propagam corretamente.

Bugs cobertos:
  - `lumina run` engolia o exit code do binário (sempre 0).
  - `lumina test` sempre saía com 0 mesmo com falhas.
  - `lumina build` não propagava falha.
  - `--help` caía em "Comando desconhecido".
"""


def _write(path, content):
    path.write_text(content)
    return str(path)


def test_help_returns_zero(run_cli):
    for flag in ("--help", "-h", "help"):
        result = run_cli(flag)
        assert result.returncode == 0, f"'{flag}' → exit {result.returncode}"
        assert "Lumina CLI" in result.stdout


def test_no_args_shows_usage(run_cli):
    result = run_cli()
    assert result.returncode == 0
    assert "Lumina CLI" in result.stdout


def test_run_propagates_exit_code(run_cli, tmp_path):
    """Programa que retorna 42 → exit code 42."""
    src = _write(
        tmp_path / "r42.lm",
        "fn main() -> int:\n"
        "    return 42\n",
    )
    result = run_cli("run", src, cwd=tmp_path)
    assert result.returncode == 42, (
        f"Esperado 42, veio {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_run_zero_exit_code(run_cli, tmp_path):
    src = _write(
        tmp_path / "r0.lm",
        'fn main() -> int:\n'
        '    print("ok")\n'
        '    return 0\n',
    )
    result = run_cli("run", src, cwd=tmp_path)
    assert result.returncode == 0
    assert "ok" in result.stdout


def test_build_failure_returns_nonzero(run_cli, tmp_path):
    """Arquivo com erro semântico → build falha com exit != 0."""
    src = _write(
        tmp_path / "bad.lm",
        'fn main() -> int:\n'
        '    let x: int = "texto"\n'
        '    return 0\n',
    )
    result = run_cli("build", src, cwd=tmp_path)
    assert result.returncode != 0, (
        f"Build deveria falhar, veio {result.returncode}\n{result.stdout}"
    )


def test_test_failure_returns_nonzero(run_cli, tmp_path):
    """`lumina test` com teste falhando → exit != 0."""
    src = _write(
        tmp_path / "fail_test.lm",
        'import "std/test"\n'
        '\n'
        'test "deve falhar":\n'
        '    return check_eq(1, 2, "1 != 2")\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n',
    )
    result = run_cli("test", src, cwd=tmp_path)
    assert result.returncode != 0, (
        f"Teste deveria falhar, veio {result.returncode}\n{result.stdout}"
    )


def test_test_success_returns_zero(run_cli, tmp_path, monkeypatch):
    monkeypatch.setenv("LUMINA_NO_COVERAGE", "1")
    src = _write(
        tmp_path / "ok_test.lm",
        'import "std/test"\n'
        '\n'
        'test "deve passar":\n'
        '    return check_eq(1, 1, "1 == 1")\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n',
    )
    result = run_cli("test", src, cwd=tmp_path)
    assert result.returncode == 0, (
        f"Teste deveria passar, veio {result.returncode}\n{result.stdout}"
    )

