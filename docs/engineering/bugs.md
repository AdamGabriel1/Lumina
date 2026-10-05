# docs/engineering/bugs.md

# 🐛 Bugs corrigidos

Lista completa de bugs silenciosos corrigidos no compilador. Todos passavam pelo CI original porque os testes só exercitavam parser/semantic — não runtime. Cada um tem teste de regressão.

**Sintoma** = o que o usuário via. **Correção** = o que mudou no código. **Teste** = arquivo de regressão.

---

## Runtime

| Bug | Sintoma | Correção | Teste |
|---|---|---|---|
| `break` / `continue` no-op | `for i in 0..100: if i == 5: break` continuava até 100 | `loop_stack` com branch para `end_bb`/`inc_bb` | `test_runtime_bugs.py` |
| `assert` sem efeito | `assert(1 == 2)` imprimia a linha seguinte e saía com 0 | `fflush(NULL)` + `abort()` + `unreachable` | `test_runtime_bugs.py` |
| `defer` inline | `defer print("b")` rodava imediatamente | `defer_stack` por função | `test_runtime_bugs.py` |
| `defer` em `if` não tomado rodava | `if false: defer print("x")` imprimia `x` | Escopo de bloco | `test_defer_scope.py` |
| `defer` em TCO era ignorado | `return self(...)` pulava defers | `_emit_all_defers()` antes do branch de TCO | `test_tco.py` |
| `and` / `or` sem short-circuit | `x != 0 and 10/x > 1` causava SIGFPE | Basic blocks + `phi i1` | `test_runtime_bugs.py` |

## Codegen

| Bug | Sintoma | Correção | Teste |
|---|---|---|---|
| Formatter apagava `@derive` | `@derive(Eq, Debug)` removido no `lumina fmt` | `_format_attrs()` | `test_runtime_bugs.py` |
| Boehm GC nunca ativava | `-lgc` era decorativo | `GC_malloc` + `call GC_init()` | `test_gc.py` |
| Match guard em enum nunca casava | `case Circle(r) if r > 10:` sempre pulava | 4 blocos por case; bind ANTES do guard | `test_match_guard_enum.py` |
| Match guard em str ignorado | `_codegen_match_with_guard` não testava voidptr | Branch de `strcmp` para voidptr | `test_match_guard_str.py` |
| Self-binding declarava `int` fixo | `case s if s.contains("x")` falhava | `variant_name is None` antes de `isinstance(binding, list)` | `test_match_guard_str.py` |
| String literal virava self-binding | `case "build":` casava qualquer string | Parser envolve literal em `StringExpr` | `test_match_guard_str.py` |
| `covered_variants` explodia com multi-pattern | `unhashable type: list` | Achata listas, ignora `None`, honra wildcard | `test_multi_pattern.py` |
| `struct` recompilado no REPL | `P is already defined` | Cada `LLVMCodegen` cria seu próprio `ir.Context()` | `cli/test_repl.py` |
| `let` em campo `int` aceitava `str` | `Ponto { x: "texto", y: 2 }` imprimia endereço | `is_assignable(field_decl_type, value_type)` por campo | `test_struct_field_types.py` |
| `Box<T>` como parâmetro não compilava | `fn put<T>(b: Box<T>, val: T)` → erro | `unify_type` + `substitute_generic` | `test_nested_generics.py` |
| LSP rename misturava escopos | Renomear `i` em `main` mexia no `i` de `helper` | `_filter_refs_for_scope` via `scope_map` | `lsp/tests/test_lsp_keys.py` |
| SCC dispatcher sem `defer_stack` | `AttributeError` em mutual TCO | Init `defer_stack` no entry + reset por membro | `test_tco_mutual.py` |
| `@attrs` sobrescritos como tuples | `@safe`/`@macro` nunca ativavam | Removido override em `parser/parser.py::parse` | `test_safe_mode.py` / `test_macros.py` |
| `read_file()` sem null check | segfault quando arquivo não existe | `phi` retorna string vazia se `fopen == NULL` | `examples/database.lm` |
| `free()` rejeitava `i64*` | `TypeError: i8* != i64*` | `bitcast` antes do call | `test_escape_analysis.py` |
| `chr`/`atoi` sem branch no codegen | retornavam `0` sempre | Branches dedicados em `calls.py` | `test_std_result.py` |
| `SliceExpr` virava `ptr` | `s[..3] == "abc"` comparava endereços | Infere tipo da fonte (`str` → `str`) | `examples/string_methods_test.lm` |
| `bool` → `int` com `sext` | `true` virava `-1` | `zext` quando origem é `i1` | `test_codegen_bugs.py` |
| `for x in arr` perdia o `N` | loop vazio (N=0) | `array_lengths` no codegen, consultado por `_visit_for_iterable` | `test_forin.py` |
| `impl Box<T>` chamado em `Box<int>` | `%"Box"* != %"Box_int_"*` | `bitcast` para o tipo base quando cai no fallback | `test_generic_impl.py` |
| `std/result::unwrap_or` usava `default` | keyword reservada | Renomeado para `fallback` | `test_std_result.py` |
| `and_then` retornava `int` para function pointers | `_require_assignable` rejeitava `Result` | Retorna `None` (tipo desconhecido) | `test_std_result.py` |
| `main` sem `ret` após tail print | `./chip8` segfaultava via `lumina-ld` | Hook `_fn_ensure_terminator` no `function_body.py` garante `ret` no fim do bloco | `examples/chip8.lm` |
| `alloca` dentro de loop estoura stack | `./gc_test` segfaultava com ~250K iterações | Variáveis locais e parâmetros alocadas no bloco de entrada (`entry_bb`) da função | `examples/gc_test.lm` |
| `var_types` como set em SCC | `AttributeError: 'set' object has no attribute 'get'` quando membro de SCC chamava função genérica | `_materialize_scc_dispatcher` inicializa `var_types` como `{name: type}` (dict), não `{type}` (set) | `test_tco_mutual.py::test_scc_member_calls_generic` |
| `alloca` de buffer temporário dentro de loop | `gc_test --linker=self` segfaultava; RSP crescia ~2 GB em 100k iterações | Novo helper `_fn_emit_alloca` insere no **fim do entry block** (via `position_before(terminator)`); aplicado em `codegen_fstring` (`literals.py`), `num_to_str` (`operators.py`) e `str_buf` (`builtins.py`) | `test_gc.py::test_gc_handles_many_allocations` |
| `_fn_emit_alloca` usava `is_terminator` | `AttributeError: 'Branch' object has no attribute 'is_terminator'` em todo build | Detecção via `opname` (`br`, `ret`, `unreachable`, `switch`, ...) | build de qualquer `.lm` |
| Global `mut X = <não-literal>` re-avaliado | `chip8` e `coroutines` liam buffers null (cada referência re-executava `alloc_bytes`) | `_emit_mutable_global` agora faz zero-init + agenda init runtime via `_deferred_globals`; init é emitida no início de `main_body` (não `entry_bb`) | `test_codegen_bugs.py`, `examples/chip8.lm`, `examples/coroutines.lm` |
| Dedup de globais `mut` entre arquivos | `DuplicatedNameError: g_CTX_SIZE` quando `std/async.lm` e `coroutines.lm` declaravam `let/mut` com mesmo nome | `_emit_mutable_global` ignora segundo registro com mesmo nome; `let` no topo continua inline-constante (não vira global) | build de `examples/coroutines.lm` |
| `generate_module` registra structs na ordem do AST | `struct Parser: tokens: TokenList` (com `TokenList` de import resolvido **depois** no AST) tinha `tokens` tipado como `i64`; leitura (`p.tokens.size`) retornava 0 mesmo após atribuição | **Pass 0** pré-popula `struct_defs` com **todas** as decls de struct/enum antes de qualquer `register_struct`; **Pass 1** registra de verdade. `register_struct`/`register_enum` são idempotentes. | `bootstrap_ast_test.sh tests/fixtures` |
| `register_struct` sem on-demand + `.as_pointer()` | Campo struct referenciava tipo ainda não visto → `get_llvm_type` caía no fallback `i64` **by value**; `ir.Constant(struct_ty, 0)` no phi da safe-nav quebrava o llvmlite com `TypeError: 'int' object is not iterable` | Se `ft in struct_defs` mas não em `struct_types`, registra on-demand; depois `.as_pointer()` para campos struct (obrigatório — structs Lumina são por ponteiro) | `bootstrap_ast_test.sh tests/fixtures` / `test_nested_generics.py` |

## Semantic

| Bug | Sintoma | Correção | Teste |
|---|---|---|---|
| `lumina lint` estourava `RecursionError` | recursão mútua `_collect_vars`/`_collect_exprs` | Reescrito como `_collect` única | `test_lint.py` |
| Variante de enum com payload usada bare | `let x = Some` compilava silenciosamente | Semantic rejeita se variante tem payload | `test_enum_bare_variant.py` |
| `fn_name` usado como valor | `sort(arr, n, _cmp_asc)` → "Variável não declarada" | Semantic retorna `"fn"`, codegen bitcast p/ voidptr | `test_sort.py` |
| Indirect call com N args | `cmp(a, b)` só passava `a` | `fn_ty = i64 (i64) * n_args` | `test_sort.py` |
| `impl Box<T>:` chamando método base | `%"Box"* != %"Box_int_"*` | Bitcast no `codegen_method_call` fallback | `test_generic_impl.py` |
| **`_analyze_for` tipava `x: int` hardcoded** | **`for x in ["a","b"]: let y: str = x` falhava no semantic, apesar do codegen iterar `i8*` corretamente** | **`_infer_for_elem_type` infere tipo do array literal, `array_elem_types` ou hint `for x: T in arr`** | **`test_for_hint_type.py::test_without_hint_string_inference_works`, `test_int_array_with_str_annotation_fails`** |

## Stdlib / Builtins

| Bug | Sintoma | Correção | Teste |
|---|---|---|---|
| `stdin`/`stdout`/`stderr` fora de `BUILTIN_RET` | `std/io.lm` falhava com "Tipo inválido para parâmetro 'stream': esperado 'str', obteve 'int'" | `BUILTIN_RET` centralizado em `lumina/builtins.py` | `test_std_io.py` |
| `extern fn fgets` colidia com builtin | `TypeError: Type of #2 arg mismatch: i64 != i32` | `generate_module` pula `ExternDecl` que colide com builtin | `test_std_io.py` |
| `getchar` retornava `i32` | `ret i32 %getchar_call` não casava com `-> int` | `sext i32 → i64` em `calls.py` | `test_std_io.py` |
| `visit_ReturnStmt` sem `iN → i64` | qualquer builtin que devolvesse i32 quebrava o ret | Normalização defensiva `iN → i64` | `test_std_io.py` |
| `"\n"` em fonte virava 2 bytes literais | `fputs("\n", out)` imprimia `\n` literal | Lexer processa escapes em compile-time | `test_std_io.py` / `test_lexer.py` |
| `read_line` com `buf[n-1] = 0` | newline não era removido da linha lida | Loop explícito em `std/io.lm` | `test_std_io.py` |
| `_handle_indent` não era chamado | todos os blocos indentados falhavam com "Esperado INDENT, mas encontrei X" | Restaurada chamada em `tokenize()` | `test_lexer.py::test_indent_dedent` |

## Closures & Macros

| Bug | Sintoma | Correção | Teste |
|---|---|---|---|
| Closure com captura como callback segfaultava | `sort_by(arr, n, fn(a, b): (b-a)*mult)` passava bloco `{fn_ptr, env_ptr}` como fn ptr cru | Tipo `fn` unificado em fat pointer; `_call_closure` em toda indireta | `test_sort.py::test_sort_closure_captures` |
| `_validate_macro` rejeitava declaração multi-statement | macro multi-statement não podia ser declarada | Validação só verifica corpo não-vazio; exigência de `return <expr>` fica no call site de expressão | `test_macro_stmts.py` |
| `parse_struct` usava `expect(IDENT)` no tipo do campo | `struct S: cb: fn(int) -> int` falhava com "Esperado IDENT, mas encontrei FN ('fn')" | `parse_type()` (mesmo helper de params/enums/traits) | `test_fn_struct_fields.py` |

## Generics

| Bug | Sintoma | Correção | Teste |
|---|---|---|---|
| `get_llvm_param_type` inconsistente | `TypeError: cannot store %"Box_int_" to %"Box_int_"**` em `fn get(b: BI)` | `get_llvm_type` força monomorphização antes de checar `struct_types`; structs sempre devolvem ponteiro | `test_generic_type_alias.py::test_generic_alias_inside_fn_sig` |
| `impl Box<T>:` registrava `Box_T__get` | `Método 'get' não implementado para 'Box'` | Parser normaliza `impl Box<T>:` → nome base `Box` (se args são todos type params únicos maiúsculos) | `test_impl_box_generic.py::test_generic_impl_still_works_as_fallback` |
| Semantic procurava `Box_get`, existia `Box_int__get` | `Método 'get' não implementado` mesmo com `impl Getter for Box<int>` | Lookup tenta nome completo (`mangle_method`) e cai para base | `test_impl_box_generic.py::test_impl_trait_for_box_int` |
| `struct_defs["Custom<int>"]` não registrado | `KeyError: 'Custom<int>'` em `_construct_enum` | `get_or_create_monomorphized_{struct,enum}` registra sob chave canônica **e** mangled | `test_generic_enums.py` |
| `visit_VarDecl` forçava tipo default de enum | `bitcast Custom_int_* → Custom_int_` inválido em `let c = Wrap(42)` | Se `val.type` já é ponteiro para struct identificada, usa `val.type` como tipo do slot | `test_generic_enums.py::test_generic_enum_str_payload` |

## CLI

| Bug | Sintoma | Correção | Teste |
|---|---|---|---|
| CLI engolia exit code | `lumina run` sempre saía com 0 | `cmd_run` propaga exit | `cli/test_exit_codes.py` |
| `test` com falhas saía com 0 | `lumina test` retornava 0 | `cmd_test` retorna nº de falhas | `cli/test_exit_codes.py` |
| `--help` caía em "comando desconhecido" | — | `main()` trata `-h`/`--help`/`help`/sem args | `cli/test_exit_codes.py` |
| `_compile_extra_objects` ignorava `extra_flags` | `.cpp` sem `-DFOO=42` | Passa `linker_extra_flags` para clang/clang++ | `cli/test_build.py` |

## Linker

| Bug | Sintoma | Correção | Teste |
|---|---|---|---|
| `main` sintético em runtime | Todo link com `--linker=self` abortava com `multiple definition of 'main'` | Remoção de `int main` residual do `rt.c` + filtro em `build_gsyms` para nunca aceitar `main` de runtime | `linker/triagem.sh` |
| `main` duplicado tinha ordem dependente | O resultado do link dependia da ordem dos `.o` na linha de comando | Filtro em `build_gsyms` (não em `add_gsym`) — comportamento determinístico | `linker/triagem.sh` |
| Otimizador O1 usava API removida | `module 'llvmlite.binding' has no attribute 'create_pass_manager_builder'` (llvmlite >= 0.42) | `_optimize_ir` detecta em runtime qual API existe: `create_new_module_pass_manager()`, `create_pass_manager_builder()` ou `PassManagerBuilder`; fallback via passes individuais | build com O1 ativo |
| W^X ausente | Um único `PT_LOAD` RWX violava W^X em kernels hardened | Dois `PT_LOAD`: RX (headers + `.text` + `.rodata`) e RW (`.data` + `.bss` + heap folga); page-align entre as regiões | `readelf -l` |
| `pthread_create` incompatível com libc | `threads.lm` falhava com exit=1 sob `--linker=self` | Assinatura trocada para `pthread_t*` (compatível libc); tabela `tid → _PThread` interna; `CLONE_CHILD_CLEARTID` para join via futex | `linker/triagem.sh examples` |
| `rdi` no clobber list do clone | `asm-specifier for input or output variable conflicts with asm clobber list` ao compilar `rt.c` | Removido `"rdi"` do clobber em `_clone_pthread` — `popq %rdi` interno restaura antes de qualquer `call` | `clang -Wall -Wextra rt.c` |

## Self-hosting (parser.lm / lexer.lm)

Bugs do parser self-hosted (`.lm`) que só apareceram quando o binário passou a rodar de verdade. Não são bugs do compilador — são bugs do próprio parser — mas são silenciosos e vale registrar os padrões.

| Bug | Sintoma | Correção | Teste |
|---|---|---|---|
| `expect()` não consumia o token no sucesso | Todo parse travava em loop: `expect` retornava sem avançar `pos`, e o único `consume` era no caminho de erro (1 token consumido por erro). Saída era uma sequência infinita de `Erro: Esperado X, encontrei Y` até runaway | `if self.check(t_type) == 1: self.consume(); return`. Análogo ao `base.py::expect` que faz `return self.consume()` | `bootstrap_ast_test.sh` |
| `match` como nome de método | `fn match(...)` colidia com keyword reservada (`TokenType.MATCH`); parser não parseava | Renomeado para `try_match` (convenção clara: tenta consumir, retorna 1/0) | `bootstrap_test.sh` |
| Globais `mut node_*: ptr` sem inicializador | Codegen descartava silenciosamente o global (só emite `_emit_mutable_global` se `decl.value is not None`); toda leitura caía em `ir.Constant(i64, 0)`. Sintoma: arena toda zero, `p.tokens.size = 0` mesmo após atribuição | Inicializadores explícitos (`mut node_kinds = alloc(MAX_NODES)`) + `init_parser` só zera `node_count`. **O bug do compilador por trás continua aberto** (ver "não corrigidos") | `bootstrap_ast_test.sh` |
| `parse_switch` reconsomia `T_MATCH` | `parse_switch` chamava `parse_match_stmt` que faz `self.consume(T_MATCH)` — mas `T_SWITCH` já tinha sido consumido; o parser lia `match` como próximo token e errava | Extraído `_parse_match_body(cond)` (corpo compartilhado); `parse_switch` chama direto | `examples/` (arquivos com `switch`) |
| `_expect_gt_for_type` não splittava `T_SHR` | `Vec<Vec<int>>` falhava: lexer emite um único `T_SHR` no final, mas são sintaticamente dois `>`. Parser esperava `T_GT` e errava | Flag `pending_gt` no `Parser`: nível interno consome `T_SHR` e marca 1 pendente; nível externo usa o pendente sem tocar no stream. Não muta a lista de tokens | `bootstrap_ast_test.sh` |
| `node_nexts` sobrescrito por sibling chain | CALL args e MATCH cases guardados em `node_nexts[n]`; o bloco pai (`parse_function`) faz `node_nexts[last] = stmt` e sobrescrevia. Sintoma: `print(msg)` sem argumento, `match` sem cases | `node_bodys[n]` para args/cases; `node_nexts` só para sibling chain. Novo array `node_exts` para 3º campo específico (Slice.end, For.end, struct pattern) | `bootstrap_ast_test.sh` |
| `lex_string` do `lexer.lm` não desescapa | `"hello\n"` preservava `\` + `n` como 2 chars; Python desescapa para 1 char `\n` | `lex_string` desescapa (`\n`, `\t`, `\r`, `\0`, `\a`, `\b`, `\f`, `\v`, `\\`, `\"`, `\'`). Desconhecido → preserva `\X` como 2 chars | `bootstrap_ast_test.sh examples/api.lm` |
| `_str_set`/`_str_get` ausentes | `node_str_vals[i] = s` (com `s: str`) disparava "Tipo inválido em atribuição: esperado 'int', obteve 'str'". O semantic tipa `ptr[i]` como `int` | Wrappers com cast explícito: `_str_set` faz `value as int` (ptrtoint); `_str_get` faz `as str` (inttoptr) com guarda de null | `bootstrap_test.sh` |
| Bindings de enum pattern em profundidade errada | `case Ok(v): v + 1` no dump Python emitia `VARIABLE v` na mesma profundidade do variant; self-hosted emitia em `depth+1` (`exts` do variant) | Bindings movidos de `node_exts[variant]` para `node_rights[wrapper]` | `bootstrap_ast_test.sh examples/prelude_test.lm` |
| Mangle aplicado em assinatura inteira | `_str_set(m, struct_name + "_" + _str_get(m))` fazia `Box___eq__:fn():bool` virar `Box_Box___eq__:fn():bool`. Método não era encontrado | Extrair só o nome antes do `:`; mangle só o nome; reanexar `:fn():ret` | `bootstrap_ast_test.sh examples/overload_test.lm` |
| `is_operator` detectava só sufixo `__` | `__add__` de `impl Vector2` virava método com `self` prepended (errado — operador binário não tem self) | Detecção exige `__` no **início E** no fim: `name[0]=='__' and name[n-1]=='__'` | `bootstrap_ast_test.sh examples/overload_test.lm` |
| `parse_trait` exigia corpo de método | `trait Drawable: fn draw()` sem corpo falhava com "Esperado COLON, mas encontrei NEWLINE" | `parse_trait` inlineia o parse de método: aceita `fn nome(params) -> ret` **ou** `fn nome(params) -> ret:\n corpo` | `bootstrap_ast_test.sh examples/trait_test.lm` |
| `parse_function` rejeitava params com default | `fn greet(name: str = "World")` falhava | Aceitar `= expr` após o tipo; consumir a expressão (não armazenada ainda, mas o parser avança) | `bootstrap_ast_test.sh examples/defaults_test.lm` |
| `parse_statement` rejeitava `x := expr` | `x := 10` não avançava (caía em `parse_expression` e ficava em loop até o guard de 1M) | Caso explícito: `T_IDENT` seguido de `T_COLON_ASS` vira `VarDecl(name, "inferred", value, is_mutable=1)` | `bootstrap_ast_test.sh tests/fixtures/test_short_decl.lm` |
| Parser travava em token inesperado | Qualquer token não tratado em `parse_factor` (ex: `=>` do match-expr) imprimia "Token inesperado" mas **não consumia**; o loop externo ficava preso. Guard de avanço (pos_before) limitava o dano a 1M nós antes de parar | Defense-in-depth: `parse_factor` consome o token inesperado se não for `EOF`/`NEWLINE`/`DEDENT`/`INDENT` | `bootstrap_ast_test.sh` |
| `parse_match_stmt` sempre usava cases | `match x: 200 => "OK"` (sintaxe expression) falhava com "Esperado case ou default" | Peek-ahead: se após `:` e `INDENT` o próximo token não é `CASE` nem `DEFAULT`, faz backtrack (`self.pos = saved_pos`) e chama `parse_match_expr` | `bootstrap_ast_test.sh examples/features_showcase.lm` |
| Chained comparison no self-hosted | `0 < x < 10` parseado como `(0 < x) < 10` (um BINARY) vs. Python `ChainedComparisonExpr` (3 operandos). Alinha via **desugar no dumper Python** para BINARY aninhado — sem novo tipo no self-hosted | `parse_comparison` no self-hosted acumula enquanto vê operadores; `dump_ast.py` desugariza `ChainedComparisonExpr` antes do `emit` | `bootstrap_ast_test.sh examples/features_showcase.lm` |
| `parse_test` não trocava espaços por underscore | `test "deve somar 1":` virava `FUNCTION test_deve somar 1`, mas Python vira `test_deve_somar_1` | Substitui `' '` por `'_'` no nome; `_str_set(n, "test_" + fixed_name + ":fn():int")` | `bootstrap_ast_test.sh examples/test_framework.lm` |

---

## Bugs identificados (não corrigidos)

| Bug | Sintoma | Correção sugerida | Notas |
|---|---|---|---|
| `mut X: T` no top-level sem inicializador é silenciosamente descartado | `mut node_kinds: ptr` (sem `= ...`) não gera `GlobalVariable` LLVM; toda leitura cai em `ir.Constant(i64, 0)`. Sintoma: variável sempre 0/nil, writes viram no-op silencioso | `generate_module` deveria emitir global zero-init + agendar init runtime mesmo com `decl.value is None` (hoje só emite se `decl.value is not None`); OU o semantic deveria rejeitar `mut X: T` sem init no top-level | **Workaround aplicado em `parser.lm`**: inicializador explícito (`mut node_kinds = alloc(MAX_NODES)`). O compilador ainda tem o bug |
| Enum match em `MatchStmt` vs `MatchExpr` na profundidade de NONE wrappers | Dump do self-hosted tem `NONE` wrapper com `lefts=variant`, `rights=bindings`, `bodys=body`. Python emite `NONE` + variant + bindings + body na mesma profundidade | Alinhar convenção de profundidade entre self-hosted e `dump_ast.py` — ou aceitar divergência estrutural (dumps semânticamente equivalentes, textualmente diferentes) | Não é bug — é diferença de representação. Resolvido via `dump_ast.py` adaptando ao formato do self-hosted |

---

## Convenções

- **Runtime** — comportamento em execução (branch, defer, short-circuit).
- **Codegen** — geração de IR / layout LLVM.
- **Semantic** — type checking, inferência, resolução de símbolos.
- **Stdlib / Builtins** — `std/*.lm`, FFI com libc.
- **Closures & Macros** — fat pointers, `@macro`, expansão.
- **Generics** — monomorphização, `impl Box<T>`.
- **CLI** — exit codes, flags, comportamento de comandos.
- **Linker** — `lumina-ld`, `rt.c`, relocações, W^X.
- **Self-hosting** — bugs do parser/lexer em `.lm`.

Cada entrada tem **Sintoma** (o que o usuário vê), **Correção** (o que mudou no código) e **Teste** (arquivo de regressão). A seção "não corrigidos" lista bugs identificados mas ainda abertos, com correção sugerida.