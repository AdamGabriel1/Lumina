---
tags: [lumina, docs-internals]
---

# Codegen (LLVM)

Emissão de LLVM IR via `llvmlite`, com monomorphização, TCO, escape
analysis e closures.

**Código:** `lumina/codegen/`

## Composition root

`LLVMCodegen` (`codegen.py`) herda de uma pilha de mixins:

```
LLVMCodegen(
    ExpressionCodegen,     expressions/__init__.py
    StatementCodegen,      statements/__init__.py
    SetupMixin,            setup.py
    RegistrationMixin,     registration.py
    TypesCodegen,          types.py
    GenericsMixin,         generics.py
    TraitsMixin,           traits.py
    TCOMixin,              tco.py
    FunctionBodyMixin,     function_body.py
    HelpersCodegen,        helpers.py
)
```

Cada mixin tem um conjunto de `visit_<Node>` que emite IR e retorna
o valor SSA.

Entrypoint:

```python
codegen = LLVMCodegen(target_triple=None, use_gc=True)
ir_str = codegen.generate_module(ast)
```

## Setup inicial (`setup.py`)

`setup_libc_functions()` declara no módulo LLVM:

| Função | Uso |
|---|---|
| `printf`, `snprintf` | formatação |
| `malloc`, `free` | alocação (fallback / `--no-gc`) |
| `GC_malloc`, `GC_init` | Boehm GC |
| `strcpy`, `strcat`, `strlen`, `strncpy` | strings |
| `strstr`, `strncmp`, `strcmp` | comparação/busca |
| `atoi` | parsing de inteiro |

`_emit_mutable_global(decl)` cria `GlobalVariable` para `VarDecl`
top-level mutável.

## Registro (`registration.py`)

`register_struct(node)` — cria `ir.IdentifiedStructType` com campos.

`register_enum(node)` — tipo `{ i32 tag, i64 payload0, i64 payload1, … }`
onde o número de slots é `_enum_max_payloads(node)` (maior nº de
payloads entre variantes).

`register_function(node)` — cria a `ir.Function` com assinatura
derivada de `params` e `return_type`. `main` ganha assinatura C
`i32 (i32, i8**)` + globais `__lumina_argc` / `__lumina_argv`.

`_apply_llvm_attrs(func, attrs)` — mapeia `@inline` → `alwaysinline`,
`@noinline` → `noinline`, `@cold` → `cold`, `@hot` → `inlinehint`
(LLVM `hot` é string attribute; `inlinehint` tem mesma intenção).

## Tipos e monomorphização (`types.py`)

`get_llvm_type(name)` — mapeia o tipo Lumina para LLVM.

Structs **por ponteiro** em parâmetros (`get_llvm_param_type`
devolve `ptr`). `get_llvm_type` força monomorphização **antes** de
checar `struct_types`, evitando inconsistência entre 1ª e 2ª
chamadas.

`get_or_create_monomorphized_struct("Box<int>")`:

1. Cria `%Box_int_` via `context.get_identified_type`
2. Registra em `struct_types` sob a chave canônica **e** a mangled
3. Registra em `struct_fields` (ambos)
4. Registra em `struct_defs` (ambos)
5. Retorna o tipo LLVM

O mesmo para enums (`get_or_create_monomorphized_enum`).

Mangling: `Box<int>` → `Box_int_`; `Map<str, int>` → `Map_str_int_`.

## Generics (`generics.py`)

`materialize_generic(gen_def, type_map)`:

1. Calcula o nome mangled a partir dos type args
2. Cria a `ir.Function` (se ainda não existe)
3. Salva/restaura `builder`, `symbol_table`, `var_types`,
   `current_func_name`, `defer_stack`, `closure_vars`, `_safe_mode`
4. Emite o corpo com o `type_map` aplicado
5. Marca como materializado para não repetir

`_infer_arg_type_lumina(arg_node)` — infere tipo Lumina de um arg
para popular o `type_map` (usado quando a inferência semântica não
resolveu tudo).

## TCO (`tco.py`)

**Self-recursion** (`_try_tail_call` em `statements/flow.py`):
`return f(...)` dentro da própria `f` → store dos novos args nos
slots + `br body_bb` (em vez de `call`).

**Mutual recursion** (`_compute_tail_call_sccs` + `_materialize_scc_dispatcher`):

1. Constrói grafo de tail calls entre funções
2. Tarjan para achar SCCs
3. Para cada SCC com ≥ 2 membros, cria dispatcher `__scc_N`:
   - Params: `(i32 id, <params comuns>)`
   - `switch` sobre `id` para o bloco de cada membro
   - Cada membro é envolvido por um wrapper que chama
     `__scc_N(id, args)`
4. Dentro de cada membro do SCC, `return g(...)` vira
   `store args nos slots + store id + br dispatch_bb`

Defers são emitidos **antes** do branch de TCO
(`_emit_all_defers()`).

## Escape analysis

Ver [Semântica](semantica.md#escape-analysis) para a análise.
Aqui, `_try_stack_alloc(node)` em `statements/var_decl.py`
transforma `alloc(N)` (N literal, N ≤ 4096, sem escape/free) em:

```python
arr_ty = ir.ArrayType(elem_ty, n)
arr_ptr = self.builder.alloca(arr_ty, name=node.name + "_stack")
```

`alloc_bytes(N)` usa `i8` como elemento; `alloc(N)` usa `i64`.

## Closures / fat pointers

Todo valor `fn` é `{fn_ptr: i8*, env_ptr: i8*}` no heap:

- `_emit_lambda_closure(node)` em `expressions/aggregates.py`
  1. Aloca env struct com capturas por valor
  2. Emite `__closure_N(i8* env, i64 a1, …, i64 aN) -> i64`
  3. Aloca bloco `{fn_ptr, env_ptr}`
- `_wrap_fn_as_closure(raw_func)` em `helpers.py` — envolve funções
  nomeadas usadas como valor (`env_ptr = NULL`)
- `_call_closure(name, node)` em `expressions/calls.py` desempacota
  e chama
- `&fn_name` (AddressOfExpr) devolve o **fn ptr cru** (FFI-compatível)

## @safe

`_safe_mode` é ligado por `@safe`. Em `visit_MemberExpr` e
`visit_IndexExpr` (em `expressions/members.py`), insere:

```
is_null = icmp eq obj, null
br is_null, null_bb, ok_bb
null_bb: valor = zero; br end_bb
ok_bb:   valor = load/gep; br end_bb
end_bb:  phi [valor, zero]
```

Sem `@safe`, o acesso é direto (C-style) — SIGSEGV se `obj == nil`.
`?.` (safe nav) faz o mesmo check independente de `@safe`.

## GC

`use_gc=True` (padrão): chamadas a `alloc` vão para `GC_malloc`,
`main` começa com `call GC_init()`.

`use_gc=False` (`--no-gc`, `--wasm`): `malloc`/`free` da libc.

## Macros

`@macro` tem duas expansões:

- **Expressão** (`nome(args)`) — `_expand_macro_expr` substitui os
  params pelo arg e inlineia o `return <expr>` no call site
- **Statement** (`nome!(args)`) — `_expand_macro_stmt` inlineia o
  corpo inteiro (`_substitute_in_stmt` percorre VarDecl, AssignStmt,
  IfStmt, WhileStmt, ForStmt, DeferStmt, AssertStmt)

`_validate_macro(fn)` garante que o corpo é válido (no caso de
expressão, exige `return <expr>`; no caso de statement, aceita
múltiplos statements).

## Testes

- `tests/test_codegen_bugs.py`, `test_llvm_attrs.py`
- `tests/test_tco.py`, `test_tco_mutual.py`
- `tests/test_escape_analysis.py`, `test_gc.py`
- `tests/test_closures.py`, `test_macro*.py`
- `tests/test_generic_*.py`, `test_impl_box_generic.py`

## Ver também

- [Semântica](semantica.md)
- [Runtime](runtime.md)
- [ADR 0001 — LLVM](../engineering/decisoes/0001-backend-llvm.md)
