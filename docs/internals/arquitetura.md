---
tags: [lumina, docs-internals]
---

# Arquitetura

Como o compilador Lumina funciona por dentro. Visão de pássaro; cada
estágio tem um arquivo dedicado.

**Código:** `lumina/`

## Pipeline

```
source.lm
   │
   ├─► 1. LEXER          → tokens    (lexer/lexer.py, lexer/tokens.py)
   │
   ├─► 2. PARSER         → AST       (parser/*, ast/*)
   │
   ├─► 3. SEMANTIC       → AST anot. (semantic/analyzer.py + mixins)
   │
   ├─► 4. CODEGEN        → .ll       (codegen/codegen.py + mixins)
   │
   └─► 5. LINK (clang)   → binário
```

## Estágios

- [Lexer](lexer.md) — tokenização, INDENT/DEDENT, escapes
- [Parser](parser.md) — AST, precedência, `impl` normalization
- [Semântica](semantica.md) — type checking, traits, derives, escape
- [Codegen](codegen.md) — LLVM IR, monomorphização, TCO, closures
- [Runtime](runtime.md) — Boehm GC, `std/`, fat pointers

## Estrutura do compilador

```
lumina/
├── ast/                    Nós da AST (dataclasses)
│   ├── expressions.py
│   ├── statements.py
│   └── visitor.py          Dispatch por tipo (NodeVisitor)
├── lexer/
│   ├── lexer.py            Tokenizador
│   └── tokens.py           TokenType + KEYWORDS
├── parser/
│   ├── base.py             ParserBase (consume/expect/check)
│   ├── expressions.py      Precedência + literais + types
│   ├── patterns.py         case/pattern de match
│   ├── statements.py       let/if/while/for/defer/…
│   ├── declarations.py     fn/struct/enum/impl/trait
│   └── parser.py           Orquestrador (Parser)
├── semantic/
│   ├── analyzer.py         SemanticAnalyzer
│   ├── expressions/        Mixins por tipo de expr
│   ├── statements/         Mixins por tipo de stmt
│   ├── derives.py          @derive
│   ├── trait_resolution.py Defaults de trait
│   └── types.py            PRIMITIVES + parse_fn_type
├── codegen/
│   ├── codegen.py          LLVMCodegen (composition root)
│   ├── expressions/        Mixins por tipo de expr
│   ├── statements/         Mixins por tipo de stmt
│   ├── types.py            get_llvm_type + monomorphização
│   ├── generics.py         materialize_generic
│   ├── traits.py           Trait defaults + validate_macro
│   ├── tco.py              SCCs + dispatcher
│   ├── function_body.py    Corpo de função
│   ├── setup.py            libc + GC + globais mutáveis
│   ├── registration.py     struct/enum/function + LLVM attrs
│   └── helpers.py          create_global_string + fn wrappers
├── common/
│   ├── mangle.py           mangle_type, mangle_method
│   └── colors.py           Color + HAS_COLOR
└── errors.py               LuminaError (dataclass)
```

## Mapeamento de tipos LLVM

| Lumina | LLVM |
|---|---|
| `int` | `i64` |
| `float` | `f64` |
| `bool` | `i1` |
| `str` | `i8*` |
| `ptr` | `i64*` |
| `struct P` | `%P = type { ... }` (por ponteiro em params) |
| `enum E` | `%E = type { i32, i64, ... }` (tag + payload slots) |
| `fn` / `fn(T)->R` | fat pointer `{i8* fn, i8* env}` |

## Onde estão as decisões

- [ADR 0001 — Backend LLVM](../engineering/decisoes/0001-backend-llvm.md)
- Ver também: [contributing](../contributing.md) (fluxo de adicionar features).
