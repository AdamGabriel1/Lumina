"""Comandos inválidos devem retornar exit code != 0."""


def test_unknown_command(run_cli):
    result = run_cli("comando_inexistente")
    assert result.returncode == 1
    assert "Comando desconhecido" in result.stdout
