"""Valida o output exato de uncertain_features.lm."""
import pytest


@pytest.mark.slow
@pytest.mark.e2e
def test_uncertain_features(run_cli, expected_feature_lines):
    # Caminho RELATIVO: cmd_build deriva o nome do binário do entry_file,
    # e cmd_run executa "./<binário>". Caminho absoluto quebra o "./".
    target = "tests/features/uncertain_features.lm"

    run_cli("clean")
    result = run_cli("run", target)
    output = result.stdout + result.stderr

    assert result.returncode == 0, f"Compilação/execução falhou:\n{output}"

    missing = [line for line in expected_feature_lines if line not in output]
    assert not missing, (
        f"{len(missing)} linha(s) esperadas não apareceram:\n"
        + "\n".join(f"  · {m}" for m in missing)
        + f"\n\nOutput completo:\n{output}"
    )