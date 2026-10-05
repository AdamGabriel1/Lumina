# 🤝 Contribuindo com Lumina

Obrigado pelo interesse! Este documento cobre setup, testes, estilo e o checklist de PR.

---

## Setup de desenvolvimento

### 1. Clone e crie venv

```bash
git clone https://github.com/adamgabriel701/Lumina.git
cd Lumina
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2. Pré-requisitos de sistema

```bash
# Ubuntu/Debian
sudo apt install -y llvm-14 clang libgc-dev qemu-user

# Fedora
sudo dnf install -y llvm-devel clang gc-devel qemu-user
```

### 3. Instale em modo editável

```bash
pip install -e ".[dev]"
```

### 4. Verifique que tudo funciona

```bash
pytest tests/ -q                    # 428 passed
python3 run_tests.py                # 28/28
./scripts/check_examples.sh --run   # 54 PASS / 17 SKIP / 0 FAIL
```

---

## Estrutura do projeto

Veja [Internals](internals/arquitetura.md) para detalhes de cada módulo.

```
lumina/               # Compilador
lumina_cli/           # CLI
lumina-vscode/        # Extensão VS Code + LSP
std/                  # Standard Library (.lm)
tests/                # Pytest
examples/             # Exemplos prontos
docs/                 # Esta documentação
scripts/              # Shell helpers
benchmarks/           # Benchmarks
```

---

## Estilo de código

### Python

- **Seguimos o estilo do arquivo** — não reformate PRs inteiros.
- Linhas até ~100 colunas.
- Docstrings em **português** (consistência com o código atual).
- Type hints onde ajuda (não obrigatório).
- **Sem `print` de debug** deixado no código.

### Lumina (`.lm`)

- Indentação com **4 espaços**.
- `lumina fmt` no seu arquivo antes de commitar.
- Comentários `##` acima de funções/structs documentadas (`lumina doc` os lê).

### Commits

Formato [Conventional Commits](https://www.conventionalcommits.org/):

```
<tipo>(<escopo>): <resumo curto>

<corpo opcional>

<rodapé opcional>
```

Tipos usados:

| Tipo | Uso |
|---|---|
| `feat` | Nova feature |
| `fix` | Correção de bug |
| `docs` | Documentação |
| `test` | Testes |
| `refactor` | Refatoração sem mudança de comportamento |
| `perf` | Melhoria de performance |
| `chore` | Tarefas (build, deps) |

Exemplos:

```
feat(lang): type alias genérico com substituição de params

fix(codegen): get_llvm_param_type força monomorphização antes de checar struct_types

docs: Quickstart com exemplo Hello World antes das tabelas
```

---

## Testes

### Antes de abrir PR

```bash
# Rápido (~5s) — smoke test
python3 run_tests.py

# Médio (~30s) — testes de compilador
pytest tests/ -q -x

# Completo (~2 min) — inclui CLI e smoke de exemplos
pytest tests/ -q
./scripts/check_examples.sh --run
```

### Adicionando testes

**Para um bug fix:** adicione um teste de regressão em `tests/test_<área>_bugs.py` ou no arquivo mais próximo. O padrão é:

```python
def test_bug_descricao_curta():
    src = (
        'fn main() -> int:\n'
        '    # código que reproduz o bug\n'
        '    return 0\n'
    )
    out, rc = _run(src)  # compila + executa
    assert "esperado" in out
```

**Para uma feature nova:** crie `tests/test_<feature>.py` com casos positivos e negativos.

**Para mudança no codegen:** se o IR importa, inspecione com `_build_ir(src)` (disponível em vários testes).

### Helpers comuns

A maioria dos arquivos de teste define:

```python
def _run(src):       # compila + executa, retorna (stdout, rc)
def _build(src):     # só compila, retorna CompletedProcess
def _build_ir(src):  # compila e retorna o IR
def _lines(out, wanted):  # filtra linhas que casam
```

Reuse-os em vez de reinventar.

---

## Adicionando uma feature de linguagem

Checklist típico (ordem):

1. **AST** (`lumina/ast/`) — novo nó, se necessário.
2. **Lexer** (`lumina/lexer/`) — novo token, se necessário.
3. **Parser** (`lumina/parser/`) — regra gramatical.
4. **Semantic** (`lumina/semantic/`) — type checking, escopo.
5. **Codegen** (`lumina/codegen/`) — geração de IR.
6. **Formatters** (`lumina_cli/compiler/formatter.py`) — reemissão.
7. **Testes** (`tests/test_<feature>.py`) — positivos e negativos.
8. **Docs** (`docs/linguagem.md` ou `docs/stdlib.md`).
9. **CHANGELOG.md** — entrada em `[Unreleased]`.

### Exemplo: adicionar um builtin

Builtins ficam em `lumina/builtins.py` (fonte única). Siga o padrão:

```python
BUILTIN_FUNCTIONS = frozenset({...})

BUILTIN_RET = {
    ...
    "meu_builtin": "int",  # tipo de retorno
}
```

Depois, no codegen (`lumina/codegen/expressions/builtins.py`), adicione o branch:

```python
if func_name == "meu_builtin":
    # emitir IR
    return ...
```

E um teste em `tests/test_std_<área>.py`.

---

## Adicionando um módulo `std/*`

1. Crie `std/<nome>.lm`.
2. Documente com `##` acima de cada função pública.
3. Adicione um teste em `tests/test_std_<nome>.py` (padrão: compila + executa).
4. Adicione em `docs/stdlib.md`.
5. Adicione uma linha em `README.md` (seção Standard Library).
6. Adicione em `CHANGELOG.md`.

---

## Checklist de PR

Antes de abrir:

- [ ] `pytest tests/ -q` passa (0 falhas)
- [ ] `python3 run_tests.py` passa (28/28)
- [ ] `./scripts/check_examples.sh --run` sem regressão (54 PASS / 17 SKIP / 0 FAIL)
- [ ] `lumina fmt --check <arquivos alterados>` (se mexeu em `.lm`)
- [ ] `lumina lint <arquivos alterados>` sem novos warnings
- [ ] Testes de regressão adicionados (para bug fixes)
- [ ] Docs atualizadas (linguagem, stdlib, ferramental, se aplicável)
- [ ] `CHANGELOG.md` atualizado em `[Unreleased]`
- [ ] Commit segue Conventional Commits
- [ ] Descrição do PR explica **o quê** e **por quê**

---

## Reportando bugs

Inclua:

1. **Comando exato** que reproduz (`lumina build foo.lm`, `pytest tests/...`)
2. **Saída completa** (stdout + stderr)
3. **Versão** (`lumina --version`, `python3 --version`, `llvm-config --version`)
4. **Plataforma** (Linux/macOS/WSL, arquitetura)
5. Se possível, o `.lm` mínimo que reproduz o bug

Bugs de **runtime** são os mais valiosos — se o programa compila mas dá resultado errado ou segfault, inclua o output esperado vs o obtido.

---

## Áreas onde ajuda é bem-vinda

Do [Roadmap](../README.md#️-roadmap):

- **Safe-by-default global** (sem `@safe` explícito)
- **Macros com quasiquote**
- **Self-hosting (bootstrapping)** — compilador em Lumina
- **Package registry**
- **Code actions (quick fixes) no LSP**
- **Inlay hints no LSP**

E sempre:

- Mais exemplos em `examples/`
- Documentação em `docs/`
- Cobertura de testes em áreas cinzentas (codegen de tipos exóticos, cross-compile, FFI)

---

## Dúvidas?

- Abra uma [issue](https://github.com/adamgabriel701/Lumina/issues)
- Ou veja o [README principal](../README.md) para visão geral
- Detalhes técnicos em [Internals](internals/arquitetura.md)