# README.md

# 🌟 Lumina

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![LLVM](https://img.shields.io/badge/LLVM-14%2B-blue.svg)](https://llvm.org/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?logo=python\&logoColor=white)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Active-success.svg)](#-status)
[![Tests](https://img.shields.io/badge/tests-510%20passed-brightgreen.svg)](docs/engineering/tests.md)
[![Examples](https://img.shields.io/badge/examples-55%20pass%20%2F%2016%20skip-success.svg)](examples/)
[![Benchmarks](https://img.shields.io/badge/benchmarks-5%20suites-blue.svg)](benchmarks/results/)
[![Cross-compile](https://img.shields.io/badge/cross--compile-arm64%20%7C%20armv7%20%7C%20risc--v%20%7C%20wasm-blueviolet.svg)](#-cross-compilation)
[![Linker](https://img.shields.io/badge/linker-lumina--ld-orange.svg)](docs/internals/linking.md)
[![Slices](https://img.shields.io/badge/slices-%5BT%5D-important.svg)](#-slices)

**Lumina** é uma linguagem de programação de sistemas com sintaxe limpa baseada em indentação, backend **LLVM** e foco em ergonomia moderna, controle de memória, performance e tooling.

É uma linguagem **estaticamente tipada e compilada**, sem `;` e sem `{}` como delimitadores estruturais.

A linguagem possui:

* sintaxe baseada em indentação significativa;
* inferência de tipos;
* **safe-by-default** com `@unsafe` como opt-out;
* generics e monomorphization;
* traits com métodos default;
* enums algébricos com múltiplos payloads;
* pattern matching;
* closures;
* **macros com quasiquote** (`quote:` / `~` / `~@`);
* `comptime`;
* TCO (self e mutual recursion);
* arrays tipados (int, float, str);
* **slices `[T]`** — views tipadas e com comprimento;
* Boehm GC + `--no-gc`;
* escape analysis + VLA;
* FFI;
* concorrência e I/O assíncrono;
* backend LLVM;
* JIT e REPL;
* LSP com inlay hints e code actions;
* formatter e linter;
* compilação incremental;
* cross-compilation;
* WebAssembly;
* **lexer self-hosted** em `.lm`;
* linker ELF próprio para **x86_64 Linux**.

📖 **Documentação completa em [`docs/`](docs/README.md).**

---

## ✨ Por que Lumina?

### Sintaxe que você lê em voz alta

Lumina usa indentação significativa e combina recursos modernos sem depender de blocos delimitados por `{}`.

```lumina
fn main() -> int:
    let usuario = buscar_usuario(42)?

    defer log("fim")

    usuario?.nome |> imprimir

    return 0
```

O objetivo é manter o código compacto sem sacrificar recursos normalmente encontrados em linguagens de sistemas.

### Segurança por padrão

Null checks são o comportamento padrão. Nada de `@safe` em cada função — `@unsafe` é o opt-out para hot paths que precisam de acesso direto.

```lumina
struct U:
    id: int

fn get_id(u: U) -> int:
    return u.id        # retorna 0 se u == nil

@unsafe
fn hot_get_id(u: U) -> int:
    return u.id        # SIGSEGV se u == nil — mais rápido
```

### Performance próxima de C

O backend LLVM permite que Lumina gere código nativo competitivo em workloads computacionais.

Nos benchmarks atuais, Lumina fica próxima de C em vários testes compute-bound:

* `fib`: 0.97× de C;
* `loop`: 1.01×;
* `matrix`: 0.97×.

O benchmark de alocação mostra explicitamente o custo do Boehm GC, enquanto `--no-gc` reduz significativamente esse overhead.

A metodologia completa está em [`docs/engineering/benchmarks.md`](docs/engineering/benchmarks.md).

### Slices em vez de `(ptr, len)`

Slices `[T]` são views tipadas e com comprimento — sem alocação, sem parâmetros duplos:

```lumina
fn sum(s: [float]) -> float:
    mut total = 0.0
    for x in s:
        total += x
    return total

fn main() -> int:
    let v = [1.5, 2.5, 3.5]
    print(sum(v[..]))       # view zero-copy
    return 0
```

### Metaprogramação com quasiquote

Macros podem construir AST — não apenas substituir texto:

```lumina
@macro
fn unless(cond, body):
    quote:
        if not ~cond:
            ~body

fn main() -> int:
    unless(1 > 100, print("nunca"))
    return 0
```

### Tooling completo

O ecossistema inclui:

* compilador LLVM;
* JIT;
* REPL persistente;
* LSP (hover, definition, references, rename, inlay hints, code actions);
* formatter;
* linter;
* documentação automática;
* FFI binding generator;
* build incremental;
* cross-compilation;
* Web Playground;
* linker próprio;
* **lexer self-hosted em `.lm`**.

---

# 🚀 Quickstart

## 1. Pré-requisitos

### Ubuntu/Debian

```bash
sudo apt install -y llvm-14 clang libgc-dev python3.11 python3-pip
```

### Fedora

```bash
sudo dnf install -y llvm-devel clang gc-devel python3.11
```

Para desenvolvimento completo, incluindo testes de cross-compilation:

```bash
sudo apt install -y qemu-user
```

---

## 2. Clone o projeto

```bash
git clone https://github.com/adamgabriel701/Lumina.git
cd Lumina
```

---

## 3. Instale

Para uso:

```bash
pip install -e .
```

Para desenvolvimento:

```bash
pip install -e ".[dev]"
```

---

## 4. Crie seu primeiro projeto

```bash
lumina new ola

cd ola

lumina run main.lm
```

Saída:

```text
Hello from ola!
```

---

# 👀 A linguagem em 60 segundos

Um programa combinando enums, pattern matching, guards, `for`, F-strings e I/O:

```lumina
import "std/io"

enum Resposta:
    Texto(str)
    Numero(int)
    Vazia

fn interpretar(r: Resposta) -> str:
    match r:
        case Texto(s) if s.starts_with("olá"):
            return "saudação"

        case Texto(s):
            return s

        case Numero(n):
            return $"número: {n}"

        case Vazia:
            return "—"

    return "?"

fn main() -> int:
    let respostas = [
        Texto("olá, mundo"),
        Numero(42),
        Vazia
    ]

    for i, r in respostas:
        let categoria = interpretar(r)
        write_line($"{i}: {categoria}")

    return 0
```

Saída:

```text
0: saudação
1: número: 42
2: —
```

Mais exemplos estão disponíveis em [`examples/`](examples/).

---

# 🧠 Modelo de memória

Lumina possui diferentes estratégias de gerenciamento dependendo do contexto:

| Situação                      | Comportamento                                           |
| ----------------------------- | ------------------------------------------------------- |
| `alloc(N)` com `N` variável   | Boehm GC (`GC_malloc`) se inseguro, senão VLA           |
| `alloc(N)` literal sem escape | Stack (`alloca`), quando permitido pela escape analysis |
| `alloc(N)` dinâmico seguro    | Stack (`alloca` VLA) — não em loop, no topo, sem escape |
| `free(x)` explícito           | `GC_free` quando o objeto usa GC                        |
| `--no-gc`                     | `malloc` / `free` da libc                               |
| `--target=wasm`               | `--no-gc`                                               |
| `ptr`                         | ponteiro bruto                                          |
| `str`                         | `i8*` null-terminated                                   |
| `[T]`                         | slice `{T*, i64}` — view com comprimento                |
| `nil`                         | null pointer C-style                                    |
| `none`                        | `Option::None`                                          |
| `u.id` (default)              | null check automático                                   |
| `u.id` com `@unsafe`          | acesso direto (mais rápido, mais perigoso)              |
| `u?.id`                       | navegação segura explícita                              |

O Boehm GC é inicializado antes das alocações que dependem dele.

Com `--no-gc`, Lumina pode ser utilizada em ambientes nos quais o runtime de GC não está disponível ou não é desejado.

> **Nota sobre `--linker=self`:** o linker próprio usa uma runtime
> freestanding com alocador linear sobre `brk()`. `free()` é no-op
> (sem bookkeeping para rastrear blocos vivos). Programas com alto
> churn de alocação vão consumir RAM proporcional ao **total** de
> alocações, não ao número de alocações vivas. Use `std/alloc.lm`
> (arena) para churn controlado sob `--linker=self`.

Mais detalhes em [`docs/internals.md`](docs/internals.md).

---

# 🔥 Features por tema

## Sistema de tipos

* **Inferência estática** em retornos, lambdas, expressões binárias, generics, `Option<T>`, tuplas, slices e `comptime`.
* **Enums multi-payload** com variantes bare.
* **Pattern matching** com:

  * guards;
  * multi-pattern;
  * wildcard;
  * destructuring;
  * self-binding;
  * **cases com corpo vazio** (fallthrough):
    ```lumina
    match n:
        case 1:
        case 2:
            print("um ou dois")
    ```
* **Generics com monomorphization**.
* Generics aninhados.
* **Traits com métodos default**.
* Especialização para tipos concretos.
* **Type aliases**, inclusive genéricos e encadeados.
* **Tipos de função** como `fn(int) -> int`.
* **Tuplas** com destructuring heterogêneo.
* **Slices `[T]`** — views tipadas e com comprimento.
* Distinção entre `nil` e `none`.

## Safe-by-default

A partir da v0.7.0, null checks são o comportamento padrão:

* `u.id` com `u == nil` retorna `0` (em vez de SIGSEGV).
* `s[i]` com `i` fora dos limites em slices retorna `0`.
* `@unsafe` desliga os checks explicitamente.

Herança:

* Closures, cópias especializadas de genéricos e membros de SCCs (mutual TCO) herdam `_safe_mode`.
* `@unsafe` na função externa propaga para a closure.

## Arrays tipados

Lumina infere o **tipo do elemento** pelo primeiro elemento do array literal:

```lumina
let v = [10, 20, 30]           # [i64; 3]  — int
let precos = [1.5, 2.5, 3.5]   # [f64; 3]  — float
let nomes = ["Ana", "Bob"]     # [i8*; 2]  — str
```

Indexação preserva o tipo:

```lumina
print(precos[1])    # float (não bits do f64)
print(nomes[0])     # str   (não ponteiro formatado como int)
```

## Slices

O tipo `[T]` é uma **view** sobre região contígua de memória —
`{T*, i64}` — sem alocação.

```lumina
fn sum(s: [float]) -> float:
    mut total = 0.0
    for x in s:
        total += x
    return total

fn main() -> int:
    let v = [1.5, 2.5, 3.5]
    print(sum(v[..]))       # 7.5
    print(sum(v[1..]))      # 5.5
    return 0
```

Funciona em:

```lumina
let v = [1, 2, 3, 4, 5]
let s = v[1..4]             # [int], view de v[1..4]

print(len(s))               # 3
print(s[0])                 # 2
print(s.data)               # ptr para v[1]
print(s.len)                # 3

for x in s: print(x)        # itera 2, 3, 4

let sub = s[1..]            # [int], view dentro da view
```

Builtins:

```lumina
let p: ptr = ...
let s = as_slice(p, 10)     # [int] — view sobre p[0..10]
let w = view(p, 2, 7)       # [int] — view sobre p[2..7]
```

Sub-slicing e views são **zero-copy**.

**Nota sobre migração:** a partir da v0.8.0, `v[a..b]` retorna
`[T]` em vez de cópia `T*`. Strings mantêm retrocompat. A flag
`--legacy-slice-copy` restaura o comportamento anterior.

## Literais numéricos

Lumina aceita quatro bases:

```lumina
let a = 42          # decimal
let b = 0xFF        # hex
let c = 0b1100      # binário
let d = 0o17        # octal
let e = 3.14        # float
let f = 1e10        # float com expoente
```

## Memória e segurança

* Boehm GC por padrão.
* Escape analysis (VLA para `alloc(N)` dinâmico seguro).
* Stack allocation para determinadas alocações.
* `--no-gc`.
* **Safe-by-default** com `@unsafe` como opt-out.
* `nil` como ponteiro nulo real.
* `free`.
* Compatibilidade com FFI.

## Concorrência

Lumina possui suporte para:

* canais CSP;
* `pthread_mutex`;
* `pthread_cond`;
* green threads;
* corrotinas via `ucontext`;
* I/O assíncrono;
* `epoll`;
* `O_NONBLOCK`.

Alguns desses componentes continuam sendo **experimentais** e possuem exemplos marcados como `SKIP` na suíte de exemplos.

## Metaprogramação

### Macros com substituição

```lumina
@macro
fn dobro(x: int) -> int:
    return x * 2

fn main() -> int:
    let a = 5
    print(dobro(a + 1))   # (5+1)*2 = 12
    return 0
```

### Macros com quasiquote

`quote:` constrói AST em compile-time. `~x` interpola o AST de `x`;
`~@xs` espalha uma lista de nós.

```lumina
@macro
fn unless(cond, body):
    quote:
        if not ~cond:
            ~body

fn main() -> int:
    let x = 10
    unless(x > 100, print("pequeno"))
    return 0
```

Corpo da macro pode conter `let`, `if`, `while`, `return` para
scaffolding:

```lumina
@macro
fn choose(flag: int, a, b):
    if flag > 0:
        return quote: ~a
    return quote: ~b
```

`gensym(name)` gera bindings únicos:

```lumina
@macro
fn double(x):
    let tmp = gensym("tmp")
    quote:
        let ~tmp = ~x
        ~tmp + ~tmp
```

### Derive

```lumina
@derive(Eq, PartialEq, Debug, Display, Clone, Default)
struct User:
    id: int
    name: str
```

### Compile-time

```lumina
comptime:
    ...
```

Constant folding é realizado durante a compilação quando aplicável.

## Operadores `op=`

Formas compostas de atribuição com avaliação única do lvalue:

```lumina
mut x = 10
x += 5      # x = x + 5
x -= 3      # x = x - 3
x *= 2      # x = x * 2
x /= 4      # x = x / 4
x &= 0b1100 # x = x & 0b1100
x |= 0o7    # x = x | 0o7
x ^= 0xFF   # x = x ^ 0xFF
```

O lvalue é resolvido **uma única vez** — `arr[f()] += v` chama `f()` uma vez, não duas.

## Lexer self-hosted

O lexer em `lumina_core/lexer.lm` tem paridade funcional com o lexer
Python:

* `INDENT` / `DEDENT` via `indent_stack`.
* `paren_depth` para supressão de `NEWLINE` em `(...)`, `[...]`, `{...}`.
* Suporte a `\r\n` (CRLF).
* `0b` / `0o` / `0x` — paridade com o lexer Python.
* DEDENT final + `EOF`.

O parser self-hosted está em desenvolvimento em `lumina_core/parser.lm`.

---

# 🛠️ Tooling

## Linker próprio

Lumina possui um linker ELF estático próprio:

```bash
lumina build app.lm --linker=self
```

O `lumina-ld` substitui a etapa de link convencional para o alvo **Linux x86_64**, utilizando uma runtime freestanding própria.

O resultado pode ser um executável:

```text
ELF 64-bit LSB executable, statically linked
```

sem depender do dynamic linker do sistema.

> **Importante:** o linker próprio atualmente é destinado ao **x86_64 Linux**. Cross-compilation e WebAssembly utilizam o linker LLVM/Clang.

Documentação:

[`docs/internals/linking.md`](docs/internals/linking.md)

---

## LSP

O LSP oferece recursos como:

* hover;
* go-to-definition;
* references;
* rename;
* outline;
* semantic tokens;
* **inlay hints** (tipo inferido para `let x = 10`);
* **code actions** ("Anotar tipo inferido: `x: int`");
* resolução de nomes considerando escopo.

---

## Linter

```bash
lumina lint arquivo.lm
```

Warnings disponíveis atualmente:

```text
W001
W002
W003
W004
W005
```

Para integração com ferramentas:

```bash
lumina lint arquivo.lm --format=json
```

O exit code corresponde ao número de warnings encontrados.

---

## Formatter

```bash
lumina fmt arquivo.lm
```

O formatter preserva elementos importantes do código, incluindo comentários, atributos, slices, `quote:` e `for x: T in arr`.

---

## REPL

```bash
lumina repl
```

Com comandos como:

```text
:history
:decls
:clear
```

---

## Documentação automática

```bash
lumina doc
```

Formatos disponíveis:

```bash
lumina doc --format=html
lumina doc --format=md
lumina doc --format=json
```

---

## FFI

O comando:

```bash
lumina bind header.h nome
```

gera bindings para headers C.

A integração com C/C++ continua tendo áreas que dependem do ambiente e de componentes externos.

---

# 🔗 Linker próprio

O linker é composto por:

```text
linker/
├── Makefile
├── rt.c
├── start.S
├── lumina-ld
├── test.sh
└── triagem.sh
```

A runtime freestanding implementa as operações necessárias diretamente sobre syscalls Linux.

Exemplo:

```bash
cd linker
make
```

Depois:

```bash
lumina build examples/main.lm --linker=self
```

O pipeline pode ser visualizado como:

```text
Lumina source
     │
     ▼
  Lexer
     │
     ▼
  Parser
     │
     ▼
 Semantic analysis
     │
     ▼
  LLVM IR
     │
     ▼
   clang -c
     │
     ▼
  ELF objects
     │
     ▼
 lumina-ld
     │
     ▼
Static ELF x86_64
```

A triagem atual do linker apresenta:

```text
PASS=59
FAIL-COMPILE=0
FAIL-LINK=0
FAIL-RUN=0
SKIP=12
```

Os skips correspondem a exemplos que dependem de subsistemas fora do
escopo atual do linker: pthread, raylib, FFI C++, WASM, servidores que
não terminam automaticamente e `util.lm` (módulo auxiliar sem `main`).

A lista de skip está em [`linker/skip.txt`](linker/skip.txt).

Veja [`docs/internals/linking.md`](docs/internals/linking.md) para detalhes de arquitetura, runtime, símbolos, debugging e extensão.

---

# 📚 Exemplos

O diretório [`examples/`](examples/) contém **71 arquivos** cobrindo diferentes partes da linguagem.

| Categoria             | Exemplos                                                            |
| --------------------- | ------------------------------------------------------------------- |
| **Fundamentos**       | `features.lm`, `features_showcase.lm`, `ergonomia.lm`               |
| **Generics & types**  | `generics_test.lm`, `monomorph_test.lm`, `nested_generics.lm`       |
| **Closures & HOFs**   | `lambda_test.lm`, `iter_test.lm`, `iterator_test.lm`                |
| **Traits & impls**    | `trait_test.lm`, `trait_default_test.lm`, `overload_test.lm`        |
| **Pattern matching**  | `match_expr_test.lm`, `match_struct_test.lm`, `destructure_test.lm` |
| **Macros**            | `comptime_test.lm`, `macro_test.lm`                                 |
| **Concorrência**      | `threads.lm`, `coroutines.lm`, `async_server.lm`                    |
| **I/O e web**         | `http_framework.lm`, `server.lm`, `proxy.lm`                        |
| **FFI & raylib**      | `ffi_test.lm`, `chip8.lm`, `engine.lm`                              |
| **Projetos maiores**  | `json_parser.lm`, `sql_engine.lm`, `vm.lm`, `search_engine.lm`      |
| **Bare-metal & WASM** | `wasm_math.lm`, `wasm_memory.lm`, `wasm_js_interop.lm`              |

A verificação automatizada pode ser executada com:

```bash
./scripts/check_examples.sh --run
```

Resultado atual:

```text
55 PASS
16 SKIP
0 FAIL
```

---

# 📊 Status

**Active / Public Release**

O compilador possui pipeline end-to-end funcional, uma suíte extensa de testes e ferramentas suficientes para desenvolver, testar e experimentar programas reais em Lumina.

## Verificação atual

| Métrica           |                      Resultado |
| ----------------- | -----------------------------: |
| Testes `pytest`   |                 **510 passed** |
| Suite standalone  |                      **28/28** |
| Exemplos          | **55 PASS / 16 SKIP / 0 FAIL** |
| Triagem do linker | **59 PASS / 12 SKIP / 0 FAIL** |

### Pytest

```bash
pytest tests/ -q
```

Resultado:

```text
510 passed in 141.61s (0:02:21)
```

### Suite standalone

```bash
python3 run_tests.py
```

Resultado:

```text
28/28 verifications OK
```

### Exemplos

```bash
./scripts/check_examples.sh --run
```

Resultado:

```text
55 PASS / 16 SKIP / 0 FAIL
```

### Linker

```bash
./linker/triagem.sh examples
```

Resultado:

```text
PASS=59
FAIL-COMPILE=0
FAIL-LINK=0
FAIL-RUN=0
SKIP=12
```

O modo `--linker=self` produz o mesmo conjunto PASS/SKIP/FAIL que o
clang nos exemplos. Os 12 SKIP da triagem são: servidores que não
terminam sozinhos, dependências externas (raylib, C++, WASM), pthreads
(fora do escopo do runtime freestanding) e `util.lm` (módulo auxiliar
sem `main`).

## Exemplos atualmente ignorados

Os exemplos que aparecem como `SKIP` na triagem do linker incluem:

```text
api
app
async_server
engine
ffi_test
http_framework
proxy
serve
server
threads
util
wasm_js_interop
```

Os motivos variam conforme o exemplo e incluem dependências externas, subsistemas experimentais, FFI, WASM ou programas que não possuem comportamento adequado para execução automática na triagem.

Os motivos detalhados devem ser consultados em [`docs/engineering/bugs.md`](docs/engineering/bugs.md).

---

# ⚡ Performance

Os benchmarks utilizam mediana de 20 execuções, com 3 warm-ups e afinidade fixa em uma vCPU.

Host utilizado no benchmark:

| Item   | Valor                    |
| ------ | ------------------------ |
| CPU    | AMD EPYC 7763 @ 3.24 GHz |
| vCPUs  | 2 compartilhadas         |
| RAM    | 7.9 GiB                  |
| SO     | Ubuntu 24.04.4 LTS       |
| Kernel | 6.8.0-1064-azure         |

Toolchain:

| Linguagem | Configuração      |
| --------- | ----------------- |
| C         | clang 18.1.3      |
| Rust      | 1.98.1, `-O3`     |
| Go        | 1.27.0            |
| Node.js   | 24.20.0           |
| Python    | 3.14.2            |
| Lumina    | HEAD, `--release` |

## Resultados

> **Nota:** os números abaixo são do run de 2026-09-18. Re-rodar com
> `RUNS=20 WARMUP=3` numa VM calma antes de tirar conclusões — o
> ambiente Codespace tem IQR/mediana até 59% em alguns testes.

| Teste                      |   C -O3 | Rust -O3 | **Lumina --release** |      Go | **Lumina / C** |
| -------------------------- | ------: | -------: | -------------------: | ------: | -------------: |
| Fibonacci (N=35)           | 32.9 ms |  32.1 ms |          **31.9 ms** | 62.2 ms |      **0.97×** |
| Crivo de Eratóstenes (10M) | 21.8 ms |  21.7 ms |              24.3 ms | 35.9 ms |          1.11× |
| Loop matemático (100M)     | 88.1 ms |  96.8 ms |          **88.9 ms** | 82.6 ms |      **1.01×** |
| Matriz 200×200             |  5.5 ms |   8.0 ms |           **5.4 ms** | 14.3 ms |      **0.97×** |
| Alloc churn (1M)           | 13.3 ms |        — |              50.0 ms |       — |          3.77× |

## GC vs `--no-gc`

| Benchmark   |      GC |   `--no-gc` |
| ----------- | ------: | ----------: |
| primes      | 27.8 ms | **23.5 ms** |
| alloc_churn | 50.0 ms | **12.2 ms** |

O benchmark de `alloc_churn` demonstra diretamente o custo do GC em workloads com muitas pequenas alocações.

Por outro lado, `--no-gc` permite aproximar o comportamento de um runtime baseado em `malloc`/`free`.

### Observações

* Os números foram coletados em uma VM compartilhada.
* A mediana é utilizada para reduzir o impacto de outliers.
* C é compilado com **clang**, não gcc, para manter o backend de comparação alinhado com LLVM.
* `--no-gc` é especialmente relevante para workloads com alta frequência de alocações.
* Os benchmarks devem ser interpretados junto com a metodologia completa.

Metodologia, código e resultados históricos:

[`docs/engineering/benchmarks.md`](docs/engineering/benchmarks.md)

---

# 🛠️ CLI

## Projetos

```bash
lumina new meu_projeto
lumina install
lumina bind header.h nome
```

## Compilar e executar

```bash
lumina run arquivo.lm
lumina build arquivo.lm
lumina check arquivo.lm
lumina jit arquivo.lm
```

## Modos de build

```bash
lumina build app.lm --release
lumina build app.lm --debug
lumina build app.lm --wasm
lumina build app.lm --no-gc
lumina build app.lm --linker=self
```

## Targets

```bash
lumina build app.lm --target=aarch64-linux-gnu
lumina build app.lm --target=arm-linux-gnueabihf
lumina build app.lm --target=riscv64-linux-gnu
lumina build app.lm --target=i386-linux-gnu
```

## Qualidade

```bash
lumina test arquivo.lm
lumina lint arquivo.lm
lumina fmt arquivo.lm
lumina doc
```

## Interativo

```bash
lumina repl
lumina playground
```

## Manutenção

```bash
lumina clean
```

### Flags globais

```bash
--error-format=text|json
--legacy-slice-copy            # restaura cópia em v[a..b] (será removida em v0.9.0)
```

### Exit codes

| Comando | Exit code             |
| ------- | --------------------- |
| `run`   | exit code do programa |
| `test`  | número de falhas      |
| `lint`  | número de warnings    |
| `build` | `0`/`1`               |
| `check` | `0`/`1`               |

Para ferramentas de CI:

```bash
--error-format=json
```

O progresso é enviado para `stderr`, permitindo que a saída estruturada seja consumida por outras ferramentas.

Mais detalhes em [`docs/ferramental.md`](docs/ferramental.md).

---

# 🌍 Cross-compilation

Lumina suporta diferentes targets através do backend LLVM e dos toolchains disponíveis no ambiente.

```bash
lumina build app.lm --target=aarch64-linux-gnu
lumina build app.lm --target=arm-linux-gnueabihf
lumina build app.lm --target=riscv64-linux-gnu
lumina build app.lm --target=i386-linux-gnu
```

## Toolchains

Em Ubuntu/Debian:

```bash
sudo apt install -y \
    gcc-aarch64-linux-gnu \
    gcc-arm-linux-gnueabihf \
    gcc-riscv64-linux-gnu \
    qemu-user
```

Dependendo do modo de runtime utilizado, `libgc` também precisa estar disponível para o target.

Para ambientes sem Boehm GC:

```bash
lumina build app.lm --no-gc
```

### Limitação do linker próprio

O `lumina-ld` atualmente suporta:

```text
x86_64 Linux
```

Para outros targets, utilize o linker LLVM/Clang:

```bash
lumina build app.lm --linker=clang
```

---

# 🕸️ WebAssembly

Lumina também pode gerar WebAssembly.

Exemplo:

```lumina
export fn fib(n: int) -> int:
    if n <= 1:
        return n

    return fib(n - 1) + fib(n - 2)
```

Compile:

```bash
lumina build math.lm --wasm
```

O modo WASM utiliza `--no-gc`.

Exemplo de consumo:

```javascript
WebAssembly.instantiateStreaming(fetch("math.wasm"))
    .then(obj => console.log(obj.instance.exports.fib(35)));
```

---

# 🧪 Testes

Lumina possui testes em múltiplas camadas:

```text
tests/
├── parser
├── semantic
├── codegen
├── runtime
├── compiler
└── integration
```

Execute a suíte principal:

```bash
pytest tests/ -q
```

Resultado atual:

```text
510 passed in 141.61s
```

Suites adicionais:

```bash
python3 run_tests.py                    # 28/28
./scripts/check_examples.sh --run       # 55 PASS / 16 SKIP / 0 FAIL
./linker/triagem.sh examples            # PASS=59 FAIL-*=0 SKIP=12
```

---

# 🐛 Engenharia e regressões

O projeto mantém documentação específica para bugs e regressões:

[`docs/engineering/bugs.md`](docs/engineering/bugs.md)

Cada correção relevante deve, quando aplicável, possuir:

```text
sintoma
   ↓
causa
   ↓
correção
   ↓
teste de regressão
```

Entre as correções recentes estão problemas envolvendo:

* terminadores ausentes em determinados exemplos;
* stack growth causado por `alloca` dentro de loops;
* monomorphization de tipos genéricos;
* resolução de métodos em `impl`;
* nomes canônicos de tipos;
* traits default;
* closures;
* codegen de `ret void`;
* parâmetros via `argv` (bounds check em runtime);
* proteção contra dead-code elimination em benchmarks;
* init runtime de globais `mut X = <não-literal>`;
* payloads de enum com `str`/`float` (coerção bit-exact);
* arrays tipados (`f64` e `str` — preservação do tipo de elemento);
* `arr[f()] += v` chamando `f()` duas vezes;
* `i1 → i64` em slice bounds (`sext` produzia `-1` para `true`);
* cases vazios em `match` (fallthrough);
* `trait Marker:` sem corpo;
* bloco `/* */` em coluna diferente do código ao redor;
* literais binários (`0b`) e octais (`0o`);
* `lumina/common/attrs.py` ausente;
* `_analyze_for` hardcoded em `int`;
* escape analysis conservadora em subscript;
* `is_string` não computado em `visit_SliceExpr`;
* `_build_expr` retornando primitivos Python em vez de nós de AST.

---

# 📖 Documentação

| Documento                                                          | Conteúdo                           |
| ------------------------------------------------------------------ | ---------------------------------- |
| [`docs/README.md`](docs/README.md)                                 | Índice da documentação             |
| [`docs/getting-started/guia-rapido.md`](docs/getting-started/guia-rapido.md) | Instalação e primeiros passos      |
| [`docs/guia/linguagem.md`](docs/guia/linguagem.md)                 | Referência da linguagem            |
| [`docs/guia/stdlib.md`](docs/guia/stdlib.md)                       | Standard Library                   |
| [`docs/guia/ferramental.md`](docs/guia/ferramental.md)             | CLI, LSP, formatter, linter e REPL |
| [`docs/internals/arquitetura.md`](docs/internals/arquitetura.md)   | Pipeline e internals               |
| [`docs/internals/linking.md`](docs/internals/linking.md)           | Linker próprio e runtime           |
| [`docs/contributing.md`](docs/contributing.md)                     | Desenvolvimento e contribuição     |
| [`docs/engineering/bugs.md`](docs/engineering/bugs.md)             | Bugs e regressões                  |
| [`docs/engineering/tests.md`](docs/engineering/tests.md)           | Organização dos testes             |
| [`docs/engineering/benchmarks.md`](docs/engineering/benchmarks.md) | Metodologia dos benchmarks         |

ADRs:

* [`docs/engineering/decisoes/0001-backend-llvm.md`](docs/engineering/decisoes/0001-backend-llvm.md)
* [`docs/engineering/decisoes/0002-slice-types.md`](docs/engineering/decisoes/0002-slice-types.md)
* [`docs/engineering/decisoes/0003-quasiquote.md`](docs/engineering/decisoes/0003-quasiquote.md)

---

# 🤝 Contributing

Contribuições são bem-vindas.

Antes de abrir um PR:

```bash
pytest tests/ -q

python3 run_tests.py

./scripts/check_examples.sh --run

./linker/triagem.sh examples

lumina fmt --check <arquivos>

lumina lint <arquivos>
```

Se você modificou o linker:

```bash
cd linker
make clean
make
cd ..

./scripts/check_examples.sh --run --linker=self
```

Consulte [`docs/contributing.md`](docs/contributing.md) para:

* setup de desenvolvimento;
* estilo de código;
* estrutura do projeto;
* processo de contribuição;
* criação de novas features;
* testes;
* checklist de PR.

---

# 🏗️ Estrutura do projeto

```text
Lumina/
├── lumina/                 # Compilador (Python)
├── lumina_cli/             # CLI
├── lumina_core/            # Compilador self-hosted (.lm)
│   ├── lexer.lm            # Lexer em Lumina
│   └── parser.lm           # Parser em Lumina (em dev)
├── lumina-vscode/          # LSP / extensão VS Code
├── std/                    # Standard Library
├── tests/                  # Testes
├── examples/               # Exemplos
├── docs/                   # Documentação
├── scripts/                # Scripts auxiliares
├── linker/                 # lumina-ld + runtime freestanding
├── benchmarks/             # Benchmarks
├── run_tests.py            # Suite standalone
├── CHANGELOG.md            # Histórico de versões
└── README.md               # Este documento
```

---

# 🗺️ Roadmap

## Concluído

### Linguagem

* [x] Lexer/parser/AST com indentação significativa
* [x] Codegen LLVM
* [x] JIT
* [x] REPL persistente
* [x] Generics
* [x] Generics aninhados
* [x] Monomorphization
* [x] Traits
* [x] Métodos default
* [x] Pattern matching
* [x] Multi-pattern
* [x] Guards
* [x] Destructuring
* [x] Cases com corpo vazio (fallthrough)
* [x] Enums multi-payload
* [x] Enums genéricos
* [x] Payloads de enum com `str`/`float`
* [x] Type aliases
* [x] Tuplas
* [x] Closures com captura
* [x] Tipos de função
* [x] `impl Box<T>`
* [x] `impl Trait for Box<int>`
* [x] Arrays tipados (`int`, `float`, `str`)
* [x] **Slices `[T]` — views tipadas e com comprimento**
* [x] Slice de array com `end` implícito
* [x] Literais binários, octais e hex
* [x] `x op= y` com avaliação única do lvalue
* [x] **Safe-by-default global + `@unsafe` opt-out**
* [x] **`for x: T in arr` — iteração tipada**
* [x] **Escape analysis VLA para `alloc(N)` dinâmico**
* [x] **Macros com quasiquote (`quote:` / `~` / `~@`)**
* [x] `gensym()`
* [x] Boehm GC
* [x] Escape analysis
* [x] `--no-gc`
* [x] `nil`
* [x] `defer` com escopo de bloco
* [x] `@macro`
* [x] Macros multi-statement
* [x] `comptime`
* [x] `for x in arr`
* [x] `for i, x in arr`
* [x] Tail Call Optimization (self)
* [x] Mutual recursion (SCC dispatcher)

### Tooling

* [x] Formatter
* [x] Linter
* [x] `lumina doc`
* [x] LSP
* [x] **LSP: inlay hints + code actions**
* [x] FFI bindings
* [x] Build incremental
* [x] Cross-compilation
* [x] WebAssembly
* [x] `black_box(x)`
* [x] `argv(i)` com bounds check
* [x] `atoi`
* [x] Benchmarks comparáveis

### Linker / Runtime

* [x] Linker próprio
* [x] Runtime freestanding
* [x] ELF estático x86_64
* [x] Codegen de `ret void`
* [x] Hoisting de `alloca`
* [x] W^X estrito no linker próprio
* [x] Init runtime de globais `mut X = <não-literal>`

### Self-hosting

* [x] **Lexer self-hosted em `.lm`** (paridade funcional com Python)

## Em aberto

* [ ] Parser self-hosted em `.lm` (em desenvolvimento)
* [ ] Self-hosting completo / bootstrapping
* [ ] Package registry
* [ ] `bytes(s)` — slice de string como `[int]`
* [ ] `copy(s: [T]) -> ptr` — migração programática
* [ ] Migração de `std/*` para aceitar slices
* [ ] Remoção de `--legacy-slice-copy` (v0.9.x)
* [ ] Hygiene automática em macros
* [ ] `~@` em statement position
* [ ] `macro_rules!`-style pattern matching sobre AST
* [ ] `std/alloc` com arenas como primitiva de primeira classe
* [ ] Aliasing hints (`restrict` / `noalias`)
* [ ] Suporte a pthreads no linker próprio
* [ ] Linker próprio para AArch64
* [ ] Linker próprio para RISC-V
* [ ] `for x in arr` sobre `ptr` recebido como parâmetro (preservar tipo do elemento)

O roadmap é evolutivo; itens marcados como concluídos representam funcionalidades presentes no estado atual do projeto, enquanto itens em aberto não fazem parte do contrato de estabilidade atual.

Veja [`CHANGELOG.md`](CHANGELOG.md) para o histórico detalhado.

---

# 📜 Versionamento

Lumina segue [Semantic Versioning](https://semver.org/) como referência para versões públicas.

O histórico completo está em:

[`CHANGELOG.md`](CHANGELOG.md)

Para uma mudança relevante na linguagem, o changelog deve documentar:

* alteração de sintaxe;
* alteração semântica;
* impacto na compatibilidade;
* novos recursos;
* bugs corrigidos;
* testes relevantes.

### Versões recentes

* **v0.5.0** — linker próprio + runtime freestanding.
* **v0.6.0** — otimizador O1, pattern matching de structs, arrays tipados, literais binários/octais, `CompoundAssignStmt`.
* **v0.7.0** — safe-by-default, `for x: T in arr`, VLA, LSP inlay hints + code actions, lexer self-hosted.
* **v0.8.0** — slices `[T]`, builtins `as_slice`/`view`, sub-slicing zero-copy. **Breaking:** `v[a..b]` retorna `[T]`.
* **v0.9.0** — quasiquote (`quote:` / `~` / `~@`), `gensym()`, `QuoteInterpreter`.

---

# 📌 Estado atual

O estado atual do projeto pode ser resumido assim:

```text
Compiler             ████████████████████  Functional
LLVM backend         ████████████████████  Functional
Type system          ████████████████████  Functional
Generics             ████████████████████  Functional
Pattern matching     ████████████████████  Functional
Slices [T]           ████████████████████  Functional
Macros / quasiquote  ████████████████████  Functional
GC / memory          ████████████████████  Functional
CLI                  ████████████████████  Functional
LSP                  ████████████████████  Functional
Formatter/linter     ████████████████████  Functional
JIT/REPL             ████████████████████  Functional
Cross compilation    ████████████████████  Available
WebAssembly          ████████████████████  Available
Own linker            ████████████████████  x86_64 Linux
Self-hosting lexer   ████████████████████  Functional
Self-hosting parser  ████████████░░░░░░░░  In progress
Self-hosting full    ███░░░░░░░░░░░░░░░░░  Planned
Package registry     ███░░░░░░░░░░░░░░░░░  Planned
```

A suíte atual fornece uma base de regressão significativa:

```text
510 pytest tests
28/28 standalone verifications
55 example PASS
0 example FAIL
0 linker compile failures
0 linker link failures
0 linker runtime failures
```

Os `SKIP` existentes são explícitos e documentados, em vez de serem tratados como falhas silenciosas.

---

# 📦 Licença

Lumina é distribuída sob a licença **MIT**.

Veja [`LICENSE`](LICENSE).

---

# 🔗 Links

* **Repositório:** [https://github.com/adamgabriel701/Lumina](https://github.com/adamgabriel701/Lumina)
* **Documentação:** [`docs/`](docs/README.md)
* **Changelog:** [`CHANGELOG.md`](CHANGELOG.md)
* **Exemplos:** [`examples/`](examples/)
* **Benchmarks:** [`benchmarks/`](benchmarks/)
* **Issues:** [https://github.com/adamgabriel701/Lumina/issues](https://github.com/adamgabriel701/Lumina/issues)

---

<p align="center">

**Lumina — uma linguagem de sistemas construída do compilador ao linker.**

</p>
