---
tags: [lumina, docs-internals]
---

# Runtime

Não há uma runtime monolítica. O suporte em tempo de execução vem de
três fontes:

1. **libc** — `malloc`, `free`, `printf`, `strcmp`, etc.
2. **Boehm GC** — `libgc` (`GC_malloc`, `GC_init`), linkado com `-lgc`
3. **`std/*.lm`** — biblioteca padrão escrita em Lumina

**Código:** `std/` (Lumina) + `lumina_cli/commands/linking.py` +
`lumina/codegen/setup.py`

## GC

Padrão: **Boehm-Demers-Weiser** conservador. Inicializado uma vez em
`main` com `call GC_init()` (emitido por `codegen/setup.py`).
`alloc(N)` chama `GC_malloc(N * 8)`.

`--no-gc`: usa `malloc`/`free` da libc diretamente. `main` não chama
`GC_init`.

`--wasm`: força `--no-gc` (libgc não está disponível no WASI).

O flag é propagado em `lumina_cli/commands/build.py`:

```python
is_no_gc = ("--no-gc" in extra_flags) or is_wasm
codegen = LLVMCodegen(target_triple=target_triple, use_gc=not is_no_gc)
```

E na linkagem: `-lgc` só é passado se `use_gc`.

## Escape analysis em runtime

`alloc(N)` com N constante e sem escape/free vira `alloca` no stack
— nenhuma chamada de alocação. Ver
[Semântica](semantica.md#escape-analysis) e
[Codegen](codegen.md#escape-analysis).

Isso é o que faz `primes` (10M) rodar sem `GC_malloc` quando o
algoritmo permite.

## Closures em runtime

Valores `fn` são **fat pointers** `{fn_ptr, env_ptr}` no heap:

- Capturas ficam no env, copiadas por valor
- `env_ptr = NULL` para funções nomeadas usadas como valor
- `&fn_name` devolve o fn ptr cru (compatível com FFI C)

`_call_closure` desempacota antes de chamar. Ver
[Codegen](codegen.md#closures--fat-pointers).

## Defers

`defer` usa uma pilha por função (`defer_stack`). Escopo:

- Bloco (`_begin_scope` / `_end_scope` em `statements/flow.py`)
- Função (emitido no `ret`, inclusive em TCO via `_emit_all_defers`)

## `std/` — biblioteca padrão

Todos os módulos são escritos em Lumina (bootstrapped), exceto
bindings FFI:

| Categoria | Módulos |
|---|---|
| **Fundamentos** | `prelude` (auto-importado), `math`, `str`, `string` (StringBuilder), `result` |
| **Coleções** | `vector`, `map`, `set`, `deque`, `list`, `sort`, `iter` |
| **Testes / log** | `test`, `log` |
| **I/O e SO** | `io`, `fs`, `os`, `path`, `time`, `alloc` |
| **Concorrência** | `channel`, `async`, `async_fs`, `epoll`, `net`, `http` |
| **Integração** | `json`, `sqlite`, `raylib` |

`std/prelude.lm` é auto-importado por `parse_module`
(`lumina_cli/compiler/parse.py`) antes de resolver os `import` do
usuário.

### `std/alloc` (arena)

Primitiva para churn controlado: `init(cap)`, `alloc(arena, n)`,
`reset(arena)`, `destroy(arena)`. Evita `GC_malloc` em loops com
muitas alocações pequenas.

## `main` — assinatura C

`register_function` (em `codegen/registration.py`) reescreve `main`
para a assinatura C:

```
i32 main(i32 argc, i8** argv)
```

Emite globais `__lumina_argc` e `__lumina_argv` para que o código
Lumina acesse via `argv(i)` builtin. Isso é o que destrava
benchmarks parametrizados por linha de comando.

## FFI

`extern fn` gera declaração LLVM sem corpo — resolvido na linkagem
(clang, `-l` ou `extra_objects`). Tipos são mapeados diretamente:

| C | Lumina |
|---|---|
| `int`, `long`, `size_t` | `int` (i64) |
| `float`, `double` | `float` (f64) |
| `char*`, `const char*` | `str` (i8*) |
| `void*` | `str` (i8*) — ponteiro bruto |
| `char` | `int` |

## Testes

- `tests/test_gc.py`, `test_runtime_bugs.py`
- `tests/test_std_*.py` (io, math, os, path, result)
- `benchmarks/alloc_churn.lm`, `bench_runtime.lm`

## Ver também

- [Codegen](codegen.md)
- [Stdlib](../guia/stdlib.md)
- [Ferramental](../guia/ferramental.md)
- [Benchmarks](../engineering/benchmarks.md) (impacto do GC)
