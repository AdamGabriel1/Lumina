---
tags: [lumina, docs-internals]
---

# Semântica

Type checking, resolução de traits, expansão de derives e análise de
escape sobre a AST.

**Código:** `lumina/semantic/`

## Componentes

| Arquivo | Responsabilidade |
|---|---|
| `analyzer.py` | `SemanticAnalyzer` — orquestrador, escopos, `analyze()` |
| `types.py` | `PRIMITIVES`, `parse_fn_type`, `substitute_generic`, `is_assignable`, `unify_type` |
| `derives.py` | `DerivesMixin._expand_derives()` — sintetiza `__eq__`, `__ne__`, `__debug__`, `clone`, `new_X` |
| `trait_resolution.py` | `TraitResolutionMixin._resolve_trait_defaults()` |
| `expressions/` | Mixins por tipo de expressão |
| `statements/` | Mixins por tipo de statement |

## Passadas

`SemanticAnalyzer.analyze(declarations)` executa em ordem:

1. **Coleta type aliases** → `{nome: (params, target)}`
2. **Coleta macros** → `{nome: Function}` (necessário para validar `nome!(args)`)
3. **Expande `@derive`** → `DerivesMixin._expand_derives()` gera `ImplBlock`s e `Function`s sintetizadas
4. **Resolve trait defaults** → `TraitResolutionMixin._resolve_trait_defaults()` copia métodos default para cada `ImplBlock` que não os definiu
5. **Expande type aliases** → `_expand_type_aliases()` reescreve **todos** os tipos no AST (params, returns, campos, variantes, VarDecls locais)
6. **Registra símbolos** → popula `functions`, `struct_defs`, `enum_defs`, `impls`
7. **Analisa VarDecls top-level** (globais)
8. **Analisa corpos** de funções e métodos de impl

## Escopo

```python
analyzer.push_scope()                 # início de bloco
analyzer.declare_var(name, tipo, mut)
analyzer.get_var_info(name)           # {'type': ..., 'mutable': ...}
analyzer.pop_scope()
```

`self.scopes` é uma pilha de dicts. `scopes[0]` é o global, que
persiste durante `analyze_function`.

## Sistema de tipos

`PRIMITIVES = {"int", "float", "bool", "str", "ptr", "fn", "void"}`.

`parse_fn_type("fn(int, str) -> bool")` devolve
`(params, return_type)` — usado em `CallExpr` e `VarDecl` para
checar chamadas indiretas.

### `is_assignable(target, source)`

Regras principais:

- Mesmo tipo → OK
- Type param (`T`, `U`) → aceita qualquer coisa
- `int` → `float` (promoção)
- `int ↔ ptr` (cast implícito)
- `fn ↔ str ↔ ptr` (todos `i8*` no codegen)
- `nil` → `ptr`, `str`, `fn`, struct
- `Option ↔ Option<X>` (união de args)
- Struct genérica: `<T> → <T>` com mesmos args

### `unify_type` / `substitute_generic`

```python
unify_type("Box<T>", "Box<int>", {})       # True, {"T": "int"}
substitute_generic("Box<T>", {"T": "int"}) # "Box<int>"
substitute_generic("T", {"T": "int"})      # "int"
```

Usados em generics para inferir `type_map` no call site
(`semantic/expressions/calls.py`).

## Type checking por nó

Cada tipo de expressão/statement tem um `visit_*`. Exemplos:

- `visit_BinaryExpr` — infere tipo, tenta operador de struct
  (`__add__`, etc.), faz concat de strings
- `visit_StructLiteralExpr` — valida que todos os campos obrigatórios
  foram passados e que os tipos batem
- `visit_MatchStmt` — exaustividade (todos os variants cobertos ou
  wildcard)
- `visit_CallExpr` — resolve `fn_def`, named args, defaults,
  indiretas via fat pointer, generics
- `visit_VarDecl` — infere `var_type` se ausente
  (`_infer_var_decl_type`)

## Derives

`DerivesMixin._expand_derives()` transforma:

```lumina
@derive(Eq, Debug)
struct Ponto:
    x: int
    y: int
```

em `ImplBlock`s + `Function`s sintetizadas:

- `Eq` → `Ponto___eq__`, `Ponto___ne__`
- `Debug` / `Display` → `Ponto___debug__` (retorna `str`)
- `Clone` → `Ponto_clone()`
- `Default` → `new_Ponto()` (função livre)

## Trait resolution

`_resolve_trait_defaults()`:

1. Coleta `traits_by_name` de todos os `TraitDecl`
2. Para cada `ImplBlock` com `trait_name`:
   - Compara métodos explícitos com os do trait
   - Para cada default não implementado, clona a `Function` com
     `mangle_method(struct_name, method.name)`

## Escape analysis

`check_escape(node)` marca:

- `escapes` — variáveis cujo valor pode escapar da função
- `freed_vars` — variáveis passadas para `free()`

Esses conjuntos são consultados pelo codegen em
`_try_stack_alloc` (`codegen/statements/var_decl.py`): se `alloc(N)`
tem `N` constante, N ≤ 4096, e a variável não está em `escapes` nem
`freed_vars`, gera `alloca` em vez de `GC_malloc`.

## Erros

Erros são `LuminaError` com mensagem, local e sugestão ("você quis
dizer X?" via `_collect_var_refs` + Levenshtein em
`expressions/helpers.py`).

## Testes

- `tests/test_semantic.py`, `test_semantic_bugs.py`
- `tests/test_types.py`, `test_struct_field_types.py`
- `tests/test_derive_*.py`, `test_enum_bare_variant.py`,
  `test_escape_analysis.py`

## Ver também

- [Parser](parser.md)
- [Codegen](codegen.md)
- [Arquitetura](arquitetura.md)
