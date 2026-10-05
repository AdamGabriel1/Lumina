# 🔧 Ferramental

CLI, formatter, linter, REPL, LSP, playground.

---

## CLI (`lumina`)

### Comandos

```bash
lumina new <nome>              # cria projeto (lumina.toml + main.lm)
lumina build [arquivo] [flags] # compila para binário nativo
lumina run [arquivo]           # compila e executa (propaga exit code)
lumina check [arquivo]         # lexer+parser+semantic (rápido)
lumina test [arquivo]          # suíte de testes nativa
lumina jit [arquivo]           # executa via JIT
lumina clean                   # limpa cache e binários
lumina doc [flags]             # gera documentação (html/md/json)
lumina install                 # baixa dependências do lumina.toml
lumina bind <header.h> <nome>  # bindings FFI a partir de C
lumina fmt <arquivo> [--check] # formata
lumina fmt --stdin             # formata lido de stdin
lumina fmt --check-all <dir>   # verifica todos .lm de um dir
lumina repl                    # REPL interativo persistente
lumina playground [porta]      # playground web (padrão 8080)
lumina lint <arquivo> [flags]  # análise estática
lumina --help / -h / help      # ajuda
```

### Flags de build

| Flag | Efeito |
|---|---|
| `--release` | `-O3` + `opt -O2` no IR |
| `--debug` | `-O0` + DWARF |
| `--wasm` | Compila para WebAssembly (`--no-gc` implícito) |
| `--no-gc` | Bare-metal (sem Boehm GC) |
| `--target=<triple>` | Cross-compile |

### Flags globais

| Flag | Efeito |
|---|---|
| `--error-format=text\|json` | Formato de erros |

### Exit codes

| Comando | Exit code |
|---|---|
| `run` | Propaga o do binário |
| `build` | 0 se OK, ≠ 0 se falha |
| `check` | 0 se OK, ≠ 0 se erros |
| `test` | Nº de testes falhando |
| `lint` | Nº de warnings |
| `--help` | 0 |

---

## Formatter (`lumina fmt`)

Preserva:

- Comentários de linha (`#`) e bloco (`/* */`)
- Atributos (`@derive`, `@safe`, `@macro`, `@inline`, ...)
- Multi-pattern (`case A | B:`)
- Wildcard (`case _:`)
- Formatação idempotente (`fmt(fmt(x)) == fmt(x)`)

```bash
lumina fmt arquivo.lm           # formata in-place
lumina fmt arquivo.lm --check   # só verifica (exit 1 se precisa formatar)
lumina fmt --stdin              # lê de stdin, escreve em stdout
lumina fmt --check-all examples # verifica todos .lm de um dir
```

---

## Linter (`lumina lint`)

Análise estática **sem gerar código**. Exit code = nº de warnings.

### Warnings

| Código | Descrição |
|---|---|
| **W001** | Variável declarada mas nunca usada |
| **W002** | Variável sombreia outra do mesmo escopo |
| **W003** | Código inalcançável após `return`/`break`/`continue` |
| **W004** | Parâmetro de função nunca usado |
| **W005** | Função com corpo vazio |

### Uso

```bash
lumina lint app.lm                  # texto colorido
lumina lint app.lm --format=json    # JSON (pipe-safe)
lumina lint app.lm --quiet          # só exit code
```

### Supressão

Prefixe o nome com `_`:

```lumina
fn f(_unused_param: int):
    let _unused_var = 10
```

---

## REPL (`lumina repl`)

Estado **persistente** entre células:

```lumina
lumina> mut counter = 0
lumina> counter = counter + 1
lumina> counter = counter + 1
lumina> print(counter)
2
lumina> :decls
[D0] mut counter = 0
lumina> :clear
Estado limpo.
lumina> exit
```

### Comandos

| Comando | Efeito |
|---|---|
| `:help` | Lista comandos |
| `:history` | Mostra tudo que foi digitado |
| `:decls` | Mostra só declarações top-level |
| `:clear` | Limpa o estado |
| `exit` / `quit` | Sai |

### Semântica

- `mut x = 0` **persiste** entre células (vira global).
- `let x = 10` é local à célula.
- `fn`, `struct`, `enum`, `trait`, `impl` são top-level e persistem.

**Nota:** o REPL recompila tudo a cada célula (O(N²) em sessões longas). Use `:clear` para resetar.

---

## LSP (VS Code)

Servidor de linguagem implementado em `lumina-vscode/lumina_lsp.py`.

### Features

| Feature | Descrição |
|---|---|
| **Syntax highlighting** | TextMate grammar |
| **Autocomplete** | Nomes de funções, variáveis, tipos |
| **Hover** | Tipo + local, qualificado por escopo (`main::i` vs `helper::i`) |
| **Go to Definition** | Ciente de escopo |
| **Find References** | Filtra por escopo em variáveis locais |
| **Rename Symbol** | Ciente de escopo |
| **Document Symbols** | Outline com children por função |
| **Semantic Tokens** | Diferencia tipos, funções, variáveis |
| **Diagnostics** | Erros em tempo real |

### Instalação

```bash
cd lumina-vscode
npx vsce package
code --install-extension lumina-0.2.0.vsix --force
```

Ativar cores semânticas em `settings.json`:

```json
"editor.semanticHighlighting.enabled": true
```

---

## Playground Web

```bash
lumina playground              # porta 8080
lumina playground 3000         # porta custom
```

Abre em `http://localhost:8080` — editor com compilação JIT ao vivo.

Requer `playground.html` no diretório atual ou na raiz do projeto.

---

## Documentação (`lumina doc`)

Gera docs a partir de comentários `##` acima de funções, structs, enums e traits:

```lumina
## Soma dois inteiros.
## Retorna o resultado.
fn soma(a: int, b: int) -> int:
    return a + b
```

```bash
lumina doc --format=html    # docs/index.html
lumina doc --format=md      # docs/index.md
lumina doc --format=json    # docs/index.json
```

---

## Bind FFI (`lumina bind`)

Gera bindings Lumina a partir de um header C:

```bash
lumina bind sqlite3.h sqlite3
# Cria std/sqlite3.lm com extern fn para cada função do header
```

Mapeamento de tipos:

| C | Lumina |
|---|---|
| `int`, `long`, `size_t` | `int` |
| `float`, `double` | `float` |
| `char*`, `const char*` | `str` |
| `void*` | `str` |
| `char` | `int` |

---

## Cross-compile

```bash
lumina build app.lm --target=aarch64-linux-gnu      # ARM64
lumina build app.lm --target=arm-linux-gnueabihf    # ARMv7
lumina build app.lm --target=riscv64-linux-gnu      # RISC-V 64
lumina build app.lm --target=i386-linux-gnu         # x86 32-bit
lumina build app.lm --target=wasm32-wasi --wasm     # WebAssembly
```

Requer toolchain do target no PATH:

```bash
sudo apt install -y gcc-aarch64-linux-gnu gcc-arm-linux-gnueabihf \
                    gcc-riscv64-linux-gnu qemu-user
```

**Nota:** `libgc` precisa ser cross-compilada para o target, ou use `--no-gc`.

---

## Scripts auxiliares

### `run_tests.py` (standalone, ~5s)

```bash
python3 run_tests.py
# 📊 Resultado: 28/28 verificações OK
```

### `scripts/check_examples.sh`

```bash
./scripts/check_examples.sh           # só compila
./scripts/check_examples.sh --run     # compila e roda
# 📊 PASS: 54    ⏭️  SKIP: 17    ❌ FAIL: 0
```

### `scripts/run_benchmarks.sh`

```bash
./scripts/run_benchmarks.sh
```

Compara Lumina contra C, Rust, Go, Node.js e Python.