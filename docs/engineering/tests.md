# docs/engineering/tests.md

# 🧪 Testes

441 testes em 45 arquivos, organizados por camada do compilador. Todos rodam em ~2 min no CI.

---

## Rodando

```bash
pytest tests/ -v                       # tudo
pytest tests/ -k "generic"             # filtro por nome
pytest tests/test_generic_enums.py -v  # arquivo único
```

Fixtures comuns em [`tests/conftest.py`](../../tests/conftest.py):

- `lex(src)` — tokeniza
- `parse(src)` — lexer + parser
- `analyze(src)` — lexer + parser + semantic
- `run_cli(*args)` — subprocess `python -m lumina_cli`

---

## Distribuição

> **Nota:** a tabela abaixo reflete a contagem no momento em que este
> documento foi escrito. O total real é reportado pelo CI
> (`pytest tests/ -q`) e está sincronizado com o badge do `README.md`.
> Contagens por arquivo podem estar defasadas após adições recentes — trate
> este documento como **referência estrutural**, não como fonte de verdade
> numérica.

| Arquivo | Testes | Cobre |
|---|---|---|
| `test_lexer.py` | 30 | Tokens, strings, indentação, comentários |
| `test_parser.py` | 36 | Declarações, expressões, slices, fluxo |
| `test_semantic.py` | 19 | Escopo, exaustividade, traits |
| `test_types.py` | 24 | Validação de tipo |
| `test_codegen_bugs.py` | 19 | Regressão no codegen (IR + runtime) |
| `test_semantic_bugs.py` | 13 | Regressão no semantic |
| `test_runtime_bugs.py` | 9 | Runtime end-to-end |
| `test_closures.py` | 10 | Closures (captura, escopo, nested) — inclui regressão de return type |
| `test_defer_scope.py` | 7 | Escopo de defer (bloco + TCO) |
| `test_enum_bare_variant.py` | 4 | Variantes bare |
| `test_escape_analysis.py` | 4 | Escape analysis (alloca vs GC) |
| `test_forin.py` | 9 | `for x in arr` |
| `test_gc.py` | 6 | Boehm GC ativa + many allocations |
| `test_generic_impl.py` | 6 | `impl Box<T>:` |
| `test_lint.py` | 14 | `lumina lint` (W001..W005) |
| `test_macro_stmts.py` | 8 | `nome!(args)` + substituição em statements |
| `test_macros.py` | 6 | `@macro` (expressão) |
| `test_tco.py` | 7 | TCO self-recursion |
| `test_tco_mutual.py` | 7 | TCO mutual recursion + regressão `var_types` |
| `test_match_guard_enum.py` | 4 | Guard em enum |
| `test_match_guard_str.py` | 4 | Guard em str |
| `test_match_no_guard.py` | 6 | Regressão pós-refactor |
| `test_multi_pattern.py` | 8 | `case A \| B:`, wildcard |
| `test_nested_generics.py` | 6 | `Box<T>` como parâmetro |
| `test_nil.py` | 10 | `nil`, `== nil`, `?.` em nil |
| `test_struct_field_types.py` | 6 | Type check em campos |
| `test_safe_mode.py` | 6 | `@safe` |
| `test_sort.py` | 10 | `std/sort` + `for i, x in arr` + closure como callback |
| `test_std_result.py` | 9 | `std/result` helpers |
| `test_std_io.py` | 6 | `std/io` |
| `test_tuples.py` | 7 | Tuplas literais + destructuring |
| `test_fmt_comments.py` | 8 | Formatter com comentários |
| `test_fn_types.py` | 12 | Assinatura `fn(T1, T2) -> R` |
| `test_fn_struct_fields.py` | 7 | Campo fn-typed |
| `test_type_alias.py` | 8 | Type alias (primitivo, fn, struct, encadeado) |
| `test_generic_enums.py` | 2 | Enum genérico com inferência |
| `test_impl_box_generic.py` | 3 | `impl Trait for Box<int>` |
| `test_generic_type_alias.py` | 4 | Alias genérico em assinatura |
| `test_llvm_attrs.py` | 9 | `@inline`, `@cold`, `@hot` |
| `test_named_args.py` | 9 | Argumentos nomeados |
| `test_std_math.py` | 7 | `std/math` |
| `test_std_os.py` | 5 | `std/os` |
| `test_std_path.py` | 8 | `std/path` |
| `cli/test_build.py` | 2 | `new` → `build` → `run` |
| `cli/test_errors.py` | 1 | Comando desconhecido |
| `cli/test_exit_codes.py` | 7 | Exit codes + `--help` |
| `cli/test_fmt.py` | 1 | Formatter em arquivo válido |
| `cli/test_fmt_stdin.py` | 5 | `--stdin`, `--check` |
| `cli/test_repl.py` | 10 | REPL persistente |
| `features/test_examples_smoke.py` | 1 | Compila exemplos não-skipados |
| `features/test_language_features.py` | 1 | Output exato de `uncertain_features.lm` |

**Total: 441 passed.**

---

## Suites adicionais

### LSP (isolado)

```bash
cd lumina-vscode
python3 -m pytest tests/test_lsp_keys.py -v   # 8 passed
```

### Standalone (~5s, sem pytest)

```bash
python3 run_tests.py
# 📊 Resultado: 28/28 verificações OK
```

### Smoke de exemplos

```bash
./scripts/check_examples.sh --run
# 📊 PASS: 54    ⏭️  SKIP: 17    ❌ FAIL: 0
```

Os 17 skipados são servidores/sockets/threads que não terminam sozinhos — estão listados em [`tests/features/skip.txt`](../../tests/features/skip.txt).

### Triagem do linker próprio

```bash
./linker/triagem.sh examples
# PASS=59  FAIL-COMPILE=0  FAIL-LINK=0  FAIL-RUN=0  SKIP=12
```

Os 12 skipados dependem de subsistemas fora do escopo do linker próprio:
pthreads, raylib, FFI C++, WASM, servidores que não terminam. Lista
completa e motivos em [`linker/skip.txt`](../../linker/skip.txt).

---

## Filosofia de testes

- **Runtime > IR.** Quando possível, o teste **compila e executa** o binário
  (`_run`), não só inspeciona IR. O IR pode estar "correto" e o programa
  produzir resultado errado.

- **Cada bug histórico tem teste de regressão.** Ver [`bugs.md`](bugs.md).
  Quando um teste passa a falhar por causa de uma mudança de infraestrutura
  (ex.: `main` ganhando assinatura C `i32 (i32, i8**)` quebrou closures),
  a correção **não** afrouxa o teste — ela restaura a invariante que o teste
  verifica. A suíte é o contrato.

- **Negativos importam.** Para cada feature, testar também o erro esperado
  (`_build_fails`).

- **Fixtures reusadas.** Os helpers `_run`, `_build`, `_build_ir`, `_lines`
  são padrão em arquivos de teste.

- **Barreiras contra DCE em testes de benchmark.** Benchmarks que medem
  trabalho puro (ex.: `alloc_churn`, `loop`) precisam de uma barreira que o
  otimizador não atravesse. Em Lumina: `black_box(x)`. Em C: `__asm__
  __volatile__("" : : "r"(p) : "memory")`. Sem isso, clang -O3 elimina o
  loop inteiro e o teste mede zero.