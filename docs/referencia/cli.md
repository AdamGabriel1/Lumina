---
tags: [lumina, docs-referencia]
---

# Referência da CLI — `lumina`

Implementação em `lumina_cli/`. Entrypoint em `lumina_cli/main.py`
(`main()` retorna exit code inteiro 0..255).

## Sinopse

```
lumina <comando> [opções] [argumentos]
```

## Comandos

| Comando | Descrição | Módulo |
|---|---|---|
| `new <nome>` | Cria projeto (`lumina.toml` + `main.lm`) | `commands/new.py` |
| `build [arq] [flags]` | Compila `.lm` → binário | `commands/build.py` |
| `run [arq] [flags]` | Compila e executa (propaga exit) | `commands/build.py` |
| `check [arq]` | lexer + parser + semantic (sem IR) | `commands/build.py` |
| `jit [arq]` | Executa via JIT (MCJIT, sem clang) | `compiler/pipeline.py` |
| `test [arq]` | Roda funções `test_*` | `commands/test_suite.py` |
| `fmt <arq>` | Formata (in-place ou `--check`) | `commands/fmt.py` |
| `fmt --stdin` | Lê de stdin, escreve em stdout | `commands/fmt.py` |
| `fmt --check-all <dir>` | Verifica todos os `.lm` do dir | `commands/fmt.py` |
| `lint <arq>` | Análise estática (W001..W005) | `lint.py` |
| `doc [--format=X]` | Gera docs (`html`/`md`/`json`) | `commands/doc.py` |
| `repl` | REPL persistente (JIT) | `commands/repl.py` |
| `playground [porta]` | Servidor HTTP com playground JIT | `playground.py` |
| `bind <header.h> <nome>` | Gera bindings FFI | `commands/bind.py` |
| `install` | Baixa deps do `lumina.toml` | `commands/install.py` |
| `clean` | Remove artefatos de build | `commands/clean.py` |
| `--help` / `-h` / `help` | Uso | `main.py` |

## Flags globais

| Flag | Efeito |
|---|---|
| `--error-format=text\|json` | Formato dos erros (JSON é pipe-safe) |
| `--help`, `-h` | Uso + exit 0 |

## `lumina build` / `run`

`cmd_build(entry_file=None, extra_flags=[])` resolve o entrypoint
nesta ordem:

1. `entry_file` passado na linha de comando
2. `[package] entry` do `lumina.toml` (se existir)
3. `main.lm`

Flags (filtradas de `extra_flags` antes de ir pro linker):

| Flag | Efeito |
|---|---|
| `--release` | `-O3` no clang + `opt -O2` no IR |
| `--debug` | `-O0` + `-g` (DWARF) |
| `--wasm` | Compila para WebAssembly (força `--no-gc`) |
| `--no-gc` | Sem Boehm GC (usa `malloc`/`free`) |
| `--target=<triple>` | Cross-compile (`aarch64-linux-gnu`, etc.) |

Comportamento:

- `cmd_check` só roda `check_lumina` (sem gerar IR nem linkar).
- `cmd_run` chama `cmd_build` e executa o binário, **propagando o
  exit code**.
- `jit` invoca `run_jit(llvm_ir, cli_args)` — MCJIT, sem clang.
  O `main` recebe `argv`/`argc` injetados.

### Saída

- `lumina build foo.lm` → binário `./foo` (nome derivado do `.lm`)
- `lumina build` (sem arg, com `lumina.toml`) → usa `entry` e
  `package.name` como nome do binário
- WASM → `<project_name>.wasm` com `export fn` marcadas
- IR intermediário → `<project_name>.ll` no diretório atual

### Cache

`lumina build` usa cache incremental em `.lumina_cache/`:

- Chave = hash MD5 de: conteúdo dos `.lm` + fontes Python do
  compilador + flags de build (`get_cache_hash` em `utils.py`)
- Cache hit requer **três** condições:
  1. Arquivo de hash existe
  2. Hash bate (IR + `opt_flag` marker)
  3. **Binário de saída existe em disco**

Sem (3), refaz a linkagem (bug histórico: `mv` do binário depois
do build quebrava o cache).

`--wasm` e `--debug` **desabilitam** o cache.

## `lumina test`

`cmd_test(entry_file=None)`:

1. Resolve entry (mesma ordem do build)
2. `parse_module(entry)` → AST
3. Coleta funções com nome começando em `test_`
4. Gera um `main` sintético que chama cada uma e soma falhas
5. Compila com `-fprofile-instr-generate -fcoverage-mapping`
6. Executa; exit code = nº de falhas

## `lumina fmt`

Preserva:

- Comentários de linha (`#`) e bloco (`/* */`)
- `@attrs` (`@derive`, `@safe`, `@inline`, …) via `_format_attrs`
- Multi-pattern (`case A | B:`)
- Wildcard (`case _:`)

Idempotente: `fmt(fmt(x)) == fmt(x)`.

Modos:

```
lumina fmt <arquivo>              # formata in-place
lumina fmt <arquivo> --check      # só verifica (exit 1 se precisa)
lumina fmt --stdin                # stdin → stdout
lumina fmt --stdin --check        # verifica stdin
lumina fmt --check-all <dir>      # todos os .lm recursivamente
```

## `lumina lint`

`lint_file(filename, format="text", quiet=False)`. Exit code = nº de
warnings.

| Código | Descrição |
|---|---|
| **W001** | Variável declarada mas nunca usada |
| **W002** | Variável sombreia outra do mesmo escopo |
| **W003** | Código inalcançável após `return`/`break`/`continue` |
| **W004** | Parâmetro nunca usado |
| **W005** | Função com corpo vazio |

Suprime com prefixo `_`:

```lumina
fn f(_unused: int):
    let _tmp = 10
```

Flags:

```
lumina lint <arq>                 # texto colorido
lumina lint <arq> --format=json   # JSON (pipe-safe)
lumina lint <arq> --quiet         # só exit code
```

## `lumina doc`

`cmd_doc(output_format="html", output_path=None)`.

Formatos:

- `html` → `docs/index.html`
- `md` → `docs/index.md`
- `json` → `docs/index.json`

Coleta comentários `##` acima de declarações (`_collect_docs`) e
classifica por tipo (`Function`, `Struct`, `Enum`, `Trait`).

```
lumina doc
lumina doc --format=md
lumina doc --format=json
lumina doc --format=html --output=out/api.html
```

## `lumina repl`

`cmd_repl()` — JIT persistente via MCJIT.

- `mut x = 0` persiste entre células (vira global)
- `let x = 10` é local à célula
- `fn`, `struct`, `enum`, `trait`, `impl` persistem
- Cada célula é compilada como `__cell_N` e chamada
- Recompila **tudo** a cada célula (O(N²) em sessões longas)

Comandos:

| Comando | Efeito |
|---|---|
| `:help` | Lista comandos |
| `:history` | Tudo que foi digitado |
| `:decls` | Só declarações top-level |
| `:clear` | Limpa estado |
| `exit` / `quit` | Sai |

Detecta GC via `ctypes.util.find_library('gc')`; se não achar,
usa `malloc`.

## `lumina playground`

`run_server(port=8080)` — servidor HTTP em `http.server`. Procura
`playground.html` no diretório atual, raiz do projeto ou diretório
do pacote.

POST `/` com `{"code": "..."}` → compila + executa JIT e devolve
`{"success": bool, "output": str}`. Captura `stdout` via `os.dup`
do fd 1.

## `lumina bind`

`cmd_bind(header_file, output_name)` — regex em C header para
extrair assinaturas de função:

```python
pattern = r'(\w[\w\s\*]*?)\s+(\w+)\s*\(([^)]*)\)\s*;'
```

Mapeamento C → Lumina (`c_type_map`):

| C | Lumina |
|---|---|
| `int`, `long`, `size_t`, `int64_t` | `int` |
| `float`, `double` | `float` |
| `char*`, `const char*` | `str` |
| `void*` | `str` (ponteiro bruto) |
| `char` | `int` |

Gera `std/<output_name>.lm` com `extern fn` para cada função.

```
lumina bind sqlite3.h sqlite3
# → std/sqlite3.lm
```

## `lumina install`

`cmd_install()` lê `[dependencies]` de `lumina.toml`:

```toml
[dependencies]
meu_pacote = "github:usuario/repo"
```

Clona para `lumina_modules/<nome>/`:

```
https://github.com/usuario/repo.git
```

## `lumina clean`

`cmd_clean()` remove:

- `.lumina_cache/`
- Binários conhecidos: `programa_final`, `lumina_test_bin`,
  `output`, `lumina_jit_temp`
- `.ll` e `.o` gerados

## `lumina new`

`cmd_new(project_name)` cria:

```
<nome>/
├── lumina.toml
└── main.lm
```

Conteúdo de `lumina.toml`:

```toml
[package]
name = "<nome>"
version = "0.1.0"
entry = "main.lm"

[dependencies]
```

`main.lm` é um `Hello from <nome>!`.

## `lumina.toml`

Formato completo:

```toml
[package]
name = "MeuBanco"
version = "0.1.0"
entry = "main.lm"

[dependencies]
meu_pacote = "github:adamgabriel701/Lumina"

[link]
libs = ["m", "pthread", "raylib"]
extra_objects = ["examples/ffi_helper.cpp"]
extra_flags = ["-DFOO=1", "-Iinclude"]
target = "wasm32-wasi"
```

### `[link]`

Lido por `load_link_config(entry_file)`. Procura:

1. **Sidecar**: `foo.lm` → `foo.toml`
2. **Raiz**: `./lumina.toml`

Chaves:

| Chave | Efeito |
|---|---|
| `libs` | Adiciona `-l<lib>` no clang |
| `extra_objects` | Compila `.c`/`.cpp` com clang/clang++ e linka |
| `extra_flags` | Passa direto ao clang (+ `-DFOO=1`, `-Iinclude`) |
| `target` | Sobrescreve o target (mesmo efeito de `--target`) |

`compile_extra_objects()` detecta C++ pela extensão (`.cpp`, `.cc`,
`.cxx`, `.C`) e usa `clang++`. Passa `linker_extra_flags` para o
compilador do objeto (bug fix: `.cpp` com `-DFOO=42` era ignorado).

## Exit codes

| Comando | Exit code |
|---|---|
| `run` | Propaga o do binário |
| `build` | 0 se OK, ≠ 0 se falha |
| `check` | 0 se OK, ≠ 0 se erros |
| `test` | Nº de testes falhando |
| `lint` | Nº de warnings |
| `fmt` | 0 se já formatado, 1 se precisa |
| `--help` | 0 |

## Variáveis de ambiente

- **`LUMINA_ROOT`** — derivado do path do pacote (`utils.py`).
  Aponta para a raiz do repo; usado para achar `std/`.
- **`NO_COLOR`** — desabilita cores ANSI (via `_supports_color`
  em `common/colors.py`; honra `TERM=dumb` e `sys.stdout.isatty()`).

## Erros

`--error-format=json` faz erros irem para stdout como JSON
(`LuminaError.to_dict()`); progresso continua em stderr.

Formato do JSON:

```json
{
  "type": "error",
  "message": "Variável 'x' não declarada.",
  "filename": "foo.lm",
  "line": 3,
  "col": 5,
  "end_col": 6,
  "notes": ["você quis dizer 'y'?"]
}
```

## Ver também

- [Guia rápido](../getting-started/guia-rapido.md)
- [Ferramental](../guia/ferramental.md)
- [Internals › Arquitetura](../internals/arquitetura.md)
