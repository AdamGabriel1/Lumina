# 🚀 Guia Rápido

Do zero ao primeiro programa Lumina em 5 minutos.

---

## 1. Pré-requisitos

| Ferramenta | Por quê | Como instalar (Ubuntu/Debian) |
|---|---|---|
| **LLVM 14+** | Codegen (IR) | `sudo apt install llvm-14` |
| **Clang** | Link com libc/libgc | `sudo apt install clang` |
| **Boehm GC** | Garbage Collector | `sudo apt install libgc-dev` |
| **Python 3.11+** | Compilador | `sudo apt install python3.11 python3-pip` |

Em Fedora:

```bash
sudo dnf install -y llvm-devel clang gc-devel python3.11
```

---

## 2. Instalação

```bash
git clone https://github.com/adamgabriel701/Lumina.git
cd Lumina
pip install -e .
lumina --help
```

Se `lumina --help` mostrar o menu, está pronto.

---

## 3. Primeiro programa

Crie um arquivo `ola.lm`:

```lumina
fn main() -> int:
    print("Olá, Lumina!")
    return 0
```

Rode:

```bash
lumina run ola.lm
# Olá, Lumina!
```

Ou use o template de projeto:

```bash
lumina new meu_projeto
cd meu_projeto
lumina run
```

---

## 4. Sintaxe essencial (5 min)

### Funções e tipos

```lumina
fn soma(a: int, b: int) -> int:
    return a + b

fn nada() -> void:
    print("nada")
```

### Variáveis

```lumina
let x = 10          # imutável
mut y = 20          # mutável
y = y + 1           # ok
z := 30             # sintaxe curta (mutável)
```

### Controle de fluxo

```lumina
if x > 5:
    print("grande")
elif x == 5:
    print("igual")
else:
    print("pequeno")

for i in 0..10:
    print(i)

while x < 100:
    x = x + 1
```

### Listas e iteração

```lumina
let nums = [10, 20, 30]
for n in nums:
    print(n)

for i, n in nums:
    print(i, n)
```

### Pattern matching

```lumina
enum Resultado:
    Ok(int)
    Err(str)

fn tratar(r: Resultado) -> int:
    match r:
        case Ok(v):  return v
        case Err(_): return -1
    return 0
```

### Strings

```lumina
let nome = "Lumina"
let idade = 3
print($"Nome: {nome}, idade: {idade}")     # F-string
print(nome[0..3])                          # Slicing
```

### Defer (cleanup)

```lumina
fn processar() -> int:
    defer print("fim")
    print("início")
    return 0
# Saída: início / fim
```

---

## 5. CLI essencial

```bash
lumina new nome         # criar projeto
lumina run arquivo.lm   # compilar + executar
lumina build arquivo.lm # só compilar
lumina check arquivo.lm # lexer + parser + semantic (rápido)
lumina test arquivo.lm  # suíte de testes nativa
lumina repl             # REPL persistente
lumina lint arquivo.lm  # análise estática (W001..W005)
lumina fmt arquivo.lm   # formatar (preserva comentários)
lumina clean            # limpar cache e binários
```

Flags de build:

```bash
lumina build app.lm --release    # -O3 + opt -O2
lumina build app.lm --debug      # -O0 + DWARF
lumina build app.lm --wasm       # WebAssembly
lumina build app.lm --no-gc      # bare-metal (sem GC)
lumina build app.lm --target=aarch64-linux-gnu
```

---

## 6. Próximos passos

- **[Linguagem](linguagem.md)** — referência completa da sintaxe
- **[Standard Library](stdlib.md)** — `std/math`, `std/sort`, `std/io`...
- **[Ferramental](ferramental.md)** — LSP, formatter, lint, REPL
- **[Exemplos no repo](../examples/)** — 69 exemplos prontos