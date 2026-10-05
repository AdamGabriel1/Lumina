"""Configuração compartilhada dos testes."""
import sys
import os
import pathlib
import subprocess

# Garante que `lumina` e `lumina_cli` são importáveis
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from lumina.lexer import Lexer
from lumina.parser import Parser
from lumina.semantic import SemanticAnalyzer


# ============================================================
# Fixtures de parsing (usadas por tests/test_*.py)
# ============================================================
@pytest.fixture
def lex():
    """`lex(src) -> List[Token]`."""
    def _lex(src):
        return Lexer(src).tokenize()
    return _lex


@pytest.fixture
def parse():
    """`parse(src) -> List[Stmt]`."""
    def _parse(src):
        tokens = Lexer(src).tokenize()
        return Parser(tokens, "<test>", src).parse()
    return _parse


@pytest.fixture
def analyze():
    """`analyze(src) -> List[Stmt]` (roda o semantic)."""
    def _analyze(src):
        tokens = Lexer(src).tokenize()
        ast = Parser(tokens, "<test>", src).parse()
        SemanticAnalyzer("<test>", src).analyze(ast)
        return ast
    return _analyze


# ============================================================
# Fixtures da CLI (usadas por tests/cli/ e tests/features/)
# ============================================================
@pytest.fixture
def repo_root():
    """Diretório raiz do projeto (contém pyproject.toml)."""
    return pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def run_cli(repo_root):
    """Executa `python -m lumina_cli <args>` e retorna CompletedProcess."""
    def _run(*args, check=False, timeout=60, cwd=None):
        cmd = [sys.executable, "-m", "lumina_cli", *args]
        env = {**os.environ, "LUMINA_NO_COVERAGE": "1"}
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd or repo_root,
            timeout=timeout,
            check=check,
            env=env,
        )
    return _run


@pytest.fixture
def expected_feature_lines():
    """Linhas esperadas do teste end-to-end `uncertain_features.lm`.

    Mantidas em sincronia com `run_tests.py` e com o `.lm`.
    """
    return [
        "1. Slicing: ell",
        "2. Array indexing:",
        "3. Pipe: 10",
        "4. Pipe encadeado: 20",
        "5. Safe nav: 0",
        "6. Propagate: 10",
        "Segunda",
        "Ok: 5",
        "9. Short decl: 42",
        "10. Dentro do if: 100",
        "11. Início",
        "11. Defer executado",
        "11. Fim",
        "12. Assert OK",
        "13. Nome: João, Idade: 30",
        "14. Generics int: 10",
        "14. Generics float: 3.140000",
        "15. Valor profundo: 99",
        "16. Match guard: Grande",
        "17. Valor: 42",
        "18. Par: 10 20",
        "19. Cast: 10 3",
        "20. Ponteiro: 42",
        "21. Lambda: 20",
        "22. Lambda bloco: 30",
        "23. Trait default OK",
        "24. Comando: run",
        "=== Fim dos testes ===",
    ]