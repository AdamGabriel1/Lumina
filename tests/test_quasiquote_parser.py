"""Testes de parsing de `quote:`, `~`, `~@` — Fase 1 da ADR 0003.

Fase 1 é parser-only: o codegen ainda não suporta `quote:`
(levanta erro claro). Estes testes verificam que a sintaxe
parseia corretamente e produz os nós esperados.

Cobre:
  - `quote` é keyword reservada
  - `quote:` produz `QuoteExpr` com statements
  - `~x` dentro de quote → `UnquoteExpr`
  - `~@xs` dentro de quote → `UnquoteSpliceExpr`
  - `~x` fora de quote → `UnaryExpr('~', x)`
  - `~@xs` fora de quote → erro
  - `quote:` aninhado
  - `quote:` com múltiplos statements (incluindo VarDecl)
  - Formatter preserva a sintaxe
  - Bitwise NOT funciona em runtime
"""
import os
import pathlib
import subprocess
import sys
import tempfile

import pytest

from lumina.ast import (
    Function, VarDecl, ReturnStmt, NumberExpr, BinaryExpr, VariableExpr,
    UnaryExpr, QuoteExpr, UnquoteExpr, UnquoteSpliceExpr,
)
from lumina.errors import LuminaError
from lumina.lexer.tokens import TokenType


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


# ============================================================
# Lexer
# ============================================================
def test_quote_keyword_reserved(lex):
    """`quote` agora é keyword — não pode mais ser identificador."""
    toks = lex("quote")
    sig = [t for t in toks if t.type not in (
        TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT,
        TokenType.EOF, TokenType.COMMENT,
    )]
    assert len(sig) == 1
    assert sig[0].type == TokenType.QUOTE


# ============================================================
# Parser — quote:
# ============================================================
def test_quote_parses_to_quoteexpr(parse):
    src = (
        "fn f():\n"
        "    quote:\n"
        "        5\n"
    )
    ast = parse(src)
    assert len(ast) == 1
    fn = ast[0]
    assert isinstance(fn, Function)
    assert len(fn.body) == 1
    q = fn.body[0]
    assert isinstance(q, QuoteExpr)
    assert len(q.statements) == 1
    assert isinstance(q.statements[0], NumberExpr)


def test_quote_with_multiple_statements(parse):
    src = (
        "fn f():\n"
        "    quote:\n"
        "        let x = 1\n"
        "        x + 2\n"
    )
    ast = parse(src)
    q = ast[0].body[0]
    assert isinstance(q, QuoteExpr)
    assert len(q.statements) == 2
    assert isinstance(q.statements[0], VarDecl)
    assert isinstance(q.statements[1], BinaryExpr)


def test_quote_can_be_assigned(parse):
    """`let node = quote: ...` é válido sintaticamente."""
    src = (
        "fn f():\n"
        "    let node = quote:\n"
        "        5\n"
    )
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var, VarDecl)
    assert isinstance(var.value, QuoteExpr)


# ============================================================
# Parser — unquote / unquote-splice
# ============================================================
def test_unquote_inside_quote(parse):
    src = (
        "fn f():\n"
        "    quote:\n"
        "        ~x\n"
    )
    ast = parse(src)
    q = ast[0].body[0]
    assert isinstance(q, QuoteExpr)
    inner = q.statements[0]
    assert isinstance(inner, UnquoteExpr)
    assert isinstance(inner.expr, VariableExpr)
    assert inner.expr.name == "x"


def test_unquote_splice_inside_quote(parse):
    src = (
        "fn f():\n"
        "    quote:\n"
        "        ~@xs\n"
    )
    ast = parse(src)
    q = ast[0].body[0]
    inner = q.statements[0]
    assert isinstance(inner, UnquoteSpliceExpr)
    assert isinstance(inner.expr, VariableExpr)
    assert inner.expr.name == "xs"


def test_nested_quote(parse):
    """`quote:` dentro de `quote:` é válido sintaticamente."""
    src = (
        "fn f():\n"
        "    quote:\n"
        "        quote:\n"
        "            5\n"
    )
    ast = parse(src)
    outer = ast[0].body[0]
    assert isinstance(outer, QuoteExpr)
    inner = outer.statements[0]
    assert isinstance(inner, QuoteExpr)
    assert len(inner.statements) == 1
    assert isinstance(inner.statements[0], NumberExpr)


# ============================================================
# Parser — ~ fora de quote
# ============================================================
def test_tilde_outside_quote_is_bitwise_not(parse):
    src = (
        "fn f() -> int:\n"
        "    return ~5\n"
    )
    ast = parse(src)
    ret = ast[0].body[0]
    assert isinstance(ret, ReturnStmt)
    expr = ret.values[0]
    assert isinstance(expr, UnaryExpr)
    assert expr.op == '~'


def test_tilde_splice_outside_quote_errors(parse):
    """`~@` fora de `quote:` é erro em compile-time."""
    src = (
        "fn f() -> int:\n"
        "    return ~@x\n"
    )
    with pytest.raises(LuminaError, match="quote"):
        parse(src)


# ============================================================
# Reserva: `quote` não pode ser identificador
# ============================================================
def test_quote_cannot_be_identifier(parse):
    src = (
        "fn f() -> int:\n"
        "    let quote = 5\n"
        "    return 0\n"
    )
    with pytest.raises(LuminaError):
        parse(src)


# ============================================================
# Integração — bitwise NOT em runtime
# ============================================================
def test_bitwise_not_runtime():
    """`~x` executa bitwise NOT em runtime."""
    src = (
        "fn main() -> int:\n"
        "    print(~0)\n"
        "    print(~5)\n"
        "    return 0\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r1 = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
        )
        assert r1.returncode == 0, f"Build falhou:\n{r1.stdout}\n{r1.stderr}"
        r2 = subprocess.run(
            [path[:-3]], capture_output=True, text=True, timeout=10,
        )
        # ~0 = -1; ~5 = -6
        assert "-1" in r2.stdout, f"out={r2.stdout!r}"
        assert "-6" in r2.stdout, f"out={r2.stdout!r}"
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


# ============================================================
# Codegen — quote: falha com mensagem clara
# ============================================================
def test_quote_codegen_errors_clearly():
    """Usar `quote:` fora de macro → erro claro em codegen."""
    src = (
        "fn main() -> int:\n"
        "    let x = quote:\n"
        "        5\n"
        "    return 0\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
        )
        assert r.returncode != 0, f"deveria falhar:\n{r.stdout}"
        combined = r.stdout + r.stderr
        assert "quote:" in combined
        assert "macro" in combined.lower(), f"out={combined!r}"
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


# ============================================================
# Formatter preserva a sintaxe
# ============================================================
def test_formatter_preserves_quote():
    src = (
        "fn f():\n"
        "    quote:\n"
        "        ~x + 1\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "fmt", path],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r.returncode == 0, f"fmt falhou:\n{r.stderr}"
        with open(path) as fh:
            formatted = fh.read()
        assert "quote:" in formatted, f"fmt perdeu quote:\n{formatted}"
        assert "~x" in formatted, f"fmt perdeu ~x:\n{formatted}"
    finally:
        os.remove(path)
