# Exemplos Lumina

Cada `.lm` nesta pasta é um programa completo que demonstra uma ou mais features
da linguagem. Todos são compilados automaticamente pelo `scripts/check_examples.sh`.

## Executando

```bash
# Um exemplo específico
python3 -m lumina_cli build examples/hello.lm
./examples/hello

# Todos os exemplos (com contagem)
./scripts/check_examples.sh
```

## Categorias

### Fundamentos
| Arquivo | Demonstra |
|---|---|
| `main.lm` | `fn main`, variáveis, aritmética |
| `program.lm` | Impressão, chamadas de função |
| `prelude_test.lm` | Tipos `Option` e `Result` do prelude |
| `ergonomia.lm` | `:=`, `|>`, f-strings, escopo de bloco |

### Controle de fluxo
| Arquivo | Demonstra |
|---|---|
| `break_test.lm` | `break` em loops |
| `tco_test.lm` | Tail call optimization |
| `quicksort.lm` | Recursão, arrays, loops |

### Tipos e estruturas
| Arquivo | Demonstra |
|---|---|
| `struct_lit_test.lm` | Struct literals e member access |
| `destructure_test.lm` | `let (a, b) = tupla` |
| `linked_list_demo.lm` | Lista ligada com ponteiros |
| `generics_test.lm` | Funções genéricas `<T>` |
| `monomorph_test.lm` | Monomorphization de structs genéricas |

### Pattern matching
| Arquivo | Demonstra |
|---|---|
| `match_struct_test.lm` | `match` em structs |
| `match_expr_test.lm` | `match` como expressão |
| `iterator_test.lm` | Iteração com `for` |

### Traits e métodos
| Arquivo | Demonstra |
|---|---|
| `trait_test.lm` | Traits com métodos abstratos |
| `trait_default_test.lm` | Métodos default em traits |
| `string_methods_test.lm` | `std/str` |

### Funções de primeira classe
| Arquivo | Demonstra |
|---|---|
| `lambda_test.lm` | Lambdas inline |
| `overload_test.lm` | Sobrecarga de operadores (`__add__`) |

### Erros e segurança
| Arquivo | Demonstra |
|---|---|
| `safe_nav.lm` | `?.` (navegação segura) |
| `error_handling.lm` | `Result`, `?` (propagação) |
| `escape_test.lm` | Escape analysis |

### Memória
| Arquivo | Demonstra |
|---|---|
| `gc_test.lm` | Garbage collector Boehm |
| `lumina_db.lm` | Persistência em arquivo |

### Concorrência
| Arquivo | Demonstra |
|---|---|
| `threads.lm` | Threads POSIX |
| `coroutines.lm` | Green threads via ucontext |
| `async_file_test.lm` | I/O assíncrono (epoll) |

### Web
| Arquivo | Demonstra |
|---|---|
| `server.lm` | Servidor HTTP simples |
| `proxy.lm` | Proxy reverso |
| `http_framework.lm` | Framework HTTP |

### FFI (integração com C/C++)
| Arquivo | Requer | Demonstra |
|---|---|---|
| `ffi_test.lm` | `examples/ffi_helper.cpp` | Chamar C++ do Lumina |
| `engine.lm` | `libraylib` | Raylib (gráficos 2D/3D) |

### WebAssembly
| Arquivo | Requer | Demonstra |
|---|---|---|
| `wasm_math.lm` | wasi-sdk | Exportar função para JS |
| `wasm_memory.lm` | wasi-sdk | Memória linear em WASM |
| `wasm_js_interop.lm` | wasi-sdk | Chamar JS do WASM |

## Configuração de `[link]`

Alguns exemplos têm um **sidecar `.toml`** ao lado para configurar linkagem
de bibliotecas externas:

| Exemplo | Sidecar | O que configura |
|---|---|---|
| `ffi_test.lm` | `ffi_test.toml` | `extra_objects = ["ffi_helper.cpp"]` |
| `engine.lm` | `engine.toml` | `libs = ["raylib"]` |
| `wasm_js_interop.lm` | `wasm_js_interop.toml` | `target = "wasm"` |

Consulte a seção **"Configuração de Link"** no README principal para a
documentação completa de `[link]`.

## Exemplos skip

`util.lm` **não é um exemplo executável** — é um módulo auxiliar importado
por outros arquivos. Por isso não tem `fn main()`. Está em
`tests/features/skip.txt` e não é verificado pelo `check_examples.sh`.