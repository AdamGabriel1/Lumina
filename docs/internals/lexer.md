---
tags: [lumina, docs-internals]
---

# Lexer

Transforma fonte `.lm` em uma sequência de tokens.

**Código:** `lumina/lexer/`

## Componentes

| Arquivo | Responsabilidade |
|---|---|
| `lexer.py` | Classe `Lexer` — máquina de estados, `tokenize()` |
| `tokens.py` | `TokenType` (Enum), `Token`, `KEYWORDS` |

## API

```python
lexer = Lexer(source, filename="<string>")
tokens: list[Token] = lexer.tokenize()
```

`Token` tem `__slots__ = ('type', 'value', 'line', 'col', 'offset')`.

## Categorias de token

Definidas em `TokenType`:

- **Literais** — `NUMBER`, `FLOAT`, `STRING`, `TRUE`, `FALSE`, `NONE`, `NIL`
- **Identificadores** — `IDENT` (keywords resolvidas via `KEYWORDS`)
- **Keywords** — `LET CONST MUT FN RETURN IF ELIF ELSE WHILE FOR IN BREAK CONTINUE DEFER ERRDEFER MATCH CASE DEFAULT SWITCH STRUCT IMPL TRAIT ENUM IMPORT EXTERN ASSERT BENCH TEST COMPTIME EXPORT AS TYPE NOT`
- **Operadores aritméticos** — `PLUS MINUS STAR SLASH PERCENT`
- **Bitwise** — `AMP PIPE CARET TILDE SHL SHR`
- **Atribuição** — `ASSIGN PLUS_ASSIGN MINUS_ASSIGN STAR_ASSIGN SLASH_ASSIGN AMP_ASSIGN PIPE_ASSIGN CARET_ASSIGN`
- **Comparação/lógicos** — `EQ NEQ LT GT LTE GTE AND OR BANG`
- **Delimitadores** — `LPAREN RPAREN LBRACE RBRACE LBRACKET RBRACKET COMMA DOT DOT_DOT COLON COLON_ASSIGN DOUBLE_COLON SEMICOLON ARROW FAT_ARROW QUESTION AT DOLLAR`
- **Estruturais** — `COMMENT NEWLINE INDENT DEDENT EOF`

## Escapes em strings

`_ESCAPE_MAP` em `lexer.py`:

| Escape | Resultado |
|---|---|
| `\n` | newline |
| `\t` | tab |
| `\r` | carriage return |
| `\0` | NUL |
| `\a` | bell |
| `\b` | backspace |
| `\f` | form feed |
| `\v` | vertical tab |
| `\\` | backslash |
| `\"` | quote |
| `\'` | single quote |

Escapes desconhecidos preservam `\X` como dois caracteres literais.

O processamento acontece em **compile-time** (`_read_escape`), não em runtime — `"\n"` vira 1 byte no binário.

## Indentação (INDENT / DEDENT)

`_handle_indent()` mantém uma pilha de colunas. Ao fim de cada
`NEWLINE`:

- Coluna atual > topo → emite `INDENT`, empilha
- Coluna atual < topo → emite `DEDENT` (repetido até bater)
- Coluna igual → nada

Blocos são delimitados implicitamente. Não há `{` `}`.

## Comentários

Dois tipos:

- **Linha**: `# ...` → vira `TokenType.COMMENT`
- **Bloco**: `/* ... */` → `_collect_block_comment()` consome incluindo
  os delimitadores e emite um único `COMMENT`

Comentários são **preservados como tokens** para que o formatter
(`lumina fmt`) possa reemiti-los na posição correta.

## Strings interpoladas

`_string(interpolated=True)` é chamado quando o token começa com
`$"`. Gera os segmentos que o parser depois monta em
`InterpolatedStringExpr`.

## Erros

`Lexer.error(msg)` levanta `LuminaError` com `filename`, `line` e
`col` já preenchidos. Erros léxicos abortam o pipeline (não há
recuperação).

## Testes

- `tests/test_lexer.py` — 30 casos (tokens, escapes, indent/dedent,
  comentários, `_handle_indent` regression)
- `tests/test_fmt_comments.py` — verifica preservação de comentários

## Ver também

- [Parser](parser.md) — consome `list[Token]`
- [Arquitetura](arquitetura.md)
