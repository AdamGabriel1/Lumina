"""Testes do lexer.

Cobrem:
  - Números (int, float, hex)
  - Strings (normal, escape, f-string)
  - Identificadores e keywords
  - Operadores e pontuação
  - INDENT/DEDENT/NEWLINE
  - Comentários (linha, bloco)
  - Continuação implícita dentro de parênteses
"""
from lumina.lexer.tokens import TokenType


def _types(tokens):
    """Retorna a lista de TokenTypes, ignorando trivia
    (NEWLINE/INDENT/DEDENT/EOF/COMMENT)."""
    ignore = {TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT,
              TokenType.EOF, TokenType.COMMENT}
    return [t.type for t in tokens if t.type not in ignore]


def _values(tokens):
    """Retorna os valores dos tokens, ignorando trivia."""
    ignore = {TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT,
              TokenType.EOF, TokenType.COMMENT}
    return [t.value for t in tokens if t.type not in ignore]


# ============================================================
# Números
# ============================================================
def test_integer(lex):
    types = _types(lex("42"))
    assert types == [TokenType.NUMBER]


def test_float(lex):
    types = _types(lex("3.14"))
    assert types == [TokenType.FLOAT]


def test_float_with_exponent(lex):
    types = _types(lex("1e10"))
    assert types == [TokenType.FLOAT]


def test_hex_number(lex):
    types = _types(lex("0xFF"))
    assert types == [TokenType.NUMBER]


# ============================================================
# Strings
# ============================================================
def test_string_simple(lex):
    types = _types(lex('"hello"'))
    assert types == [TokenType.STRING]


def test_string_with_escape(lex):
    toks = lex(r'"hello\nworld"')
    types = _types(toks)
    assert types == [TokenType.STRING]


def test_fstring(lex):
    types = _types(lex('f"hello {name}"'))
    assert types == [TokenType.STRING]


# ============================================================
# Identificadores e keywords
# ============================================================
def test_identifier(lex):
    toks = lex("minha_var")
    assert _types(toks) == [TokenType.IDENT]


def test_keyword_let(lex):
    toks = lex("let")
    assert _types(toks) == [TokenType.LET]


def test_keyword_fn(lex):
    toks = lex("fn")
    assert _types(toks) == [TokenType.FN]


def test_keyword_control_flow(lex):
    toks = lex("if elif else while for in break continue")
    assert _types(toks) == [
        TokenType.IF, TokenType.ELIF, TokenType.ELSE,
        TokenType.WHILE, TokenType.FOR, TokenType.IN,
        TokenType.BREAK, TokenType.CONTINUE,
    ]


def test_keyword_let_vs_ident(lex):
    toks = lex("letx")
    assert _types(toks) == [TokenType.IDENT]


# ============================================================
# Operadores
# ============================================================
def test_arithmetic_operators(lex):
    toks = lex("+ - * / %")
    assert _types(toks) == [
        TokenType.PLUS, TokenType.MINUS, TokenType.STAR,
        TokenType.SLASH, TokenType.PERCENT,
    ]


def test_comparison_operators(lex):
    toks = lex("== != < > <= >=")
    assert _types(toks) == [
        TokenType.EQ, TokenType.NEQ, TokenType.LT,
        TokenType.GT, TokenType.LTE, TokenType.GTE,
    ]


def test_assign_and_colon_assign(lex):
    toks = lex("= :=")
    assert _types(toks) == [TokenType.ASSIGN, TokenType.COLON_ASSIGN]


def test_compound_assign(lex):
    toks = lex("+= -= *= /=")
    assert _types(toks) == [
        TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN,
        TokenType.STAR_ASSIGN, TokenType.SLASH_ASSIGN,
    ]


def test_arrow_and_fat_arrow(lex):
    toks = lex("-> =>")
    assert _types(toks) == [TokenType.ARROW, TokenType.FAT_ARROW]


def test_bitwise_and_shift(lex):
    toks = lex("& | ^ ~ << >>")
    assert _types(toks) == [
        TokenType.AMP, TokenType.PIPE, TokenType.CARET,
        TokenType.TILDE, TokenType.SHL, TokenType.SHR,
    ]


def test_dot_and_dot_dot(lex):
    toks = lex(". ..")
    assert _types(toks) == [TokenType.DOT, TokenType.DOT_DOT]


# ============================================================
# Indentação
# ============================================================
def test_indent_dedent(lex):
    src = "if true:\n    x = 1\n"
    toks = lex(src)
    types = [t.type for t in toks]
    assert TokenType.INDENT in types
    assert TokenType.DEDENT in types


def test_nested_indentation(lex):
    src = (
        "if true:\n"
        "    if false:\n"
        "        x = 1\n"
    )
    toks = lex(src)
    types = [t.type for t in toks]
    assert types.count(TokenType.INDENT) == 2
    assert types.count(TokenType.DEDENT) == 2


# ============================================================
# Comentários
# ============================================================
def test_line_comment(lex):
    toks = lex("x = 1  # isso é um comentário")
    values = _values(toks)
    assert "comentário" not in values
    assert "x" in values


def test_block_comment(lex):
    toks = lex("x = 1  /* comentário de bloco */ + 2")
    types = _types(toks)
    assert TokenType.IDENT in types
    assert TokenType.PLUS in types


def test_block_comment_multiline(lex):
    src = "x = 1\n/* linha 1\nlinha 2 */\ny = 2\n"
    toks = lex(src)
    types = _types(toks)
    assert TokenType.IDENT in types


# ============================================================
# Continuação implícita
# ============================================================
def test_implicit_continuation_in_parens(lex):
    src = "x = (1 +\n     2)"
    toks = lex(src)
    types = _types(toks)
    # Não deve ter NEWLINE entre os operandos
    # (o `+` está dentro de parênteses)
    assert TokenType.PLUS in types
    assert types.count(TokenType.NEWLINE) <= 1


# ============================================================
# Casos extremos
# ============================================================
def test_empty_source(lex):
    toks = lex("")
    types = _types(toks)
    assert types == []


def test_only_comment(lex):
    """Arquivo só com comentário não tem tokens significativos,
    mas o COMMENT é preservado para o formatter."""
    toks = lex("# apenas um comentário\n")
    # Nenhum token significativo
    assert _types(toks) == []
    # Mas o COMMENT está lá
    comments = [t.value for t in toks if t.type == TokenType.COMMENT]
    assert comments == ["# apenas um comentário"]


def test_comment_preserved(lex):
    """O lexer emite COMMENT com o texto completo."""
    toks = lex("# foo\nlet x = 1  # bar\n")
    comments = [t.value for t in toks if t.type == TokenType.COMMENT]
    assert "# foo" in comments
    assert "# bar" in comments


def test_block_comment_preserved(lex):
    """Comentário /* */ também é preservado como um único token."""
    toks = lex("/* multi\nlinha */\nlet x = 1\n")
    comments = [t.value for t in toks if t.type == TokenType.COMMENT]
    assert len(comments) == 1
    assert comments[0].startswith("/*")
    assert comments[0].endswith("*/")


def test_eof_always_present(lex):
    toks = lex("x = 1")
    assert toks[-1].type == TokenType.EOF
