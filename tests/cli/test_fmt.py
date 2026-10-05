"""Auto-formatter em código válido."""


def test_fmt_preserva_codigo_valido(tmp_path, run_cli):
    code = """fn main() -> int:
    print("Teste")
    return 0
"""
    file_path = tmp_path / "test_fmt.lm"
    file_path.write_text(code)

    result = run_cli("fmt", str(file_path))
    assert result.returncode == 0, f"Erro em 'lumina fmt': {result.stderr}"
    assert "formatado com sucesso" in result.stdout
    assert "fn main() -> int:" in file_path.read_text()
