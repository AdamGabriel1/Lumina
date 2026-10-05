---
tags: [lumina, docs-internals]
---

# Parser

Constrói a AST a partir dos tokens do lexer.

**Código:** `lumina/parser/`

## Hierarquia de classes

O parser é dividido em camadas por mixin, cada uma estendendo a
anterior:

```
ParserBase                  base.py           consume/expect/check, comentários
    ▲
ExpressionParser            expressions.py    precedência, literais, tipos
    ▲
PatternParser               patterns.py       case/pattern de match
    ▲
StatementParser             statements.py     let/if/while/for/defer/…
    ▲
DeclarationParser           declarations.py   fn/struct/enum/impl/trait
    ▲
Parser                      parser.py         entrypoint (.parse())
```

O orquestrador (`Parser`) despacha por token: vê `@`, lê attrs; vê
`export`, marca; vê `fn`/`struct`/`enum`/`impl`/`trait`/`type`,
delega ao método específico; senão trata como statement.

## Precedência

`parse_expression()` chama a cadeia descendente. Do mais baixo para
o mais alto:

```
logical (and/or)
  bitwise_or
    bitwise_xor
      bitwise_and
        comparison (== != < > <= >=)
          shift (<< >>)
            range (..)
              additive (+ -)
                term (* / %)
                  factor (unário, chamada, index)
                    postfix (., ?., ?, as, [])
```

Notas:

- **Comparações encadeadas** (`a < b < c`) são normalizadas em
  `(a < b) and (b < c)` (semântica Python-like).
- **Range** (`..`) fica **abaixo** de comparação — `0..n` é
  parseado como `BinaryExpr('..', 0, n)`.
- **`parse_postfix`** é chamado depois do factor para lidar com
  `.`, `?.`, `?` (propagate), `as` (cast) e `[i]` / `[a..b]`.

## `_parse_slice_or_index`

Chamado após consumir `[`. Decide entre:

- `arr[i]` → `IndexExpr`
- `arr[a..b]` → `SliceExpr(a, b)`
- `arr[a..]` → `SliceExpr(a, None)`
- `arr[..b]` → `SliceExpr(None, b)`
- `arr[..]` → `SliceExpr(None, None)`

Usa `parse_additive()` para os bounds (não `parse_expression`), para
não consumir o `..` como operador binário.

## `no_struct_literal`

Flag em `ParserBase` que evita ambiguidade entre `match x:` e
`x { y: 1 }` (struct literal). Fica `True` enquanto o parser lê a
condição de `match`; volta a `False` no corpo.

## Comentários

O parser **anexa** comentários ao nó mais próximo via
`leading_comments`:

- `_skip_comments()` / `_skip_newlines_and_comments()` consomem
  `COMMENT` e acumulam em `pending_comments`
- `_take_comments()` devolve e limpa a lista
- `parse_statement()` pega o snapshot antes de criar o nó

Isso preserva a posição original no formatter.

## Normalização de `impl`

Em `parse_impl`:

```
impl Box<T>:              → struct_name = "Box"     (base fallback)
impl Box<int>:            → struct_name = "Box<int>" (especialização)
impl Getter for Box<int>: → trait="Getter", struct="Box<int>"
```

Regra: se **todos** os args do target são type params únicos maiúsculos,
strippa o `<...>`.

Mangling canônico:

- `Box<int>` + método `greet` → `Box_int__greet`
- `Box<T>` (genérico base) + `greet` → `Box_greet`

## Atributos (`@attrs`)

`@nome` e `@nome(args)` são lidos no topo de `parse()` e anexados ao
próximo nó. Atributos reconhecidos:

- `@derive(Eq, Debug, …)`
- `@macro`
- `@safe`
- `@inline`, `@noinline`, `@cold`, `@hot`
- `export` (tratado como atributo)

## AST produzida

Definida em `lumina/ast/`:

| Onde | Nós |
|---|---|
| `ast/expressions.py` | `NumberExpr`, `StringExpr`, `BinaryExpr`, `CallExpr`, `MemberExpr`, `IndexExpr`, `SliceExpr`, `StructLiteralExpr`, `LambdaExpr`, `MatchExpr`, `CastExpr`, `AddressOfExpr`, `DerefExpr`, `PropagateExpr`, `ComptimeExpr`, `InterpolatedStringExpr`, `TupleExpr`, `ArrayExpr`, … |
| `ast/statements.py` | `Function`, `StructDecl`, `EnumDecl`, `TraitDecl`, `ImplBlock`, `VarDecl`, `AssignStmt`, `ReturnStmt`, `IfStmt`, `WhileStmt`, `ForStmt`, `MatchStmt`, `DeferStmt`, `AssertStmt`, `BenchStmt`, `MacroCallStmt`, `TypeAlias`, `ImportStmt`, `ExternDecl`, … |
| `ast/visitor.py` | `NodeVisitor.visit(node)` — dispatch por `type(node).__name__` |

## Erros

`expect(t_type, t_val)` levanta `LuminaError` com a linha e coluna do
token atual. Não há recovery — o primeiro erro aborta.

## Testes

- `tests/test_parser.py` — 36 casos
- `tests/test_fn_types.py`, `test_forin.py`, `test_tuples.py`,
  `test_type_alias.py`, `test_multi_pattern.py`

## Ver também

- [Lexer](lexer.md)
- [Semântica](semantica.md)
- [Arquitetura](arquitetura.md)
