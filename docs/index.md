---
tags: [lumina, docs]
---

# Lumina — Documentação

Linguagem de programação compilada para LLVM. Toolchain em Python,
stdlib em `.lm`, extensão VSCode com LSP.

## Por onde começar

| Você é… | Vá para |
|---|---|
| **Novo usuário** | [Guia rápido](getting-started/guia-rapido.md) |
| **Usuário diário** | [Linguagem](guia/linguagem.md) · [Stdlib](guia/stdlib.md) · [Ferramental](guia/ferramental.md) |
| **Usando a CLI** | [Referência da CLI](referencia/cli.md) |
| **Contribuidor** | [Arquitetura](internals/arquitetura.md) · [Contributing](contributing.md) |
| **Mantenedor** | [Engineering](engineering/benchmarks.md) · [ADRs](engineering/decisoes/) |

## Mapa da documentação

- `getting-started/` — instalação e primeiros passos
- `guia/` — linguagem, stdlib, ferramental
- `referencia/` — comandos da CLI, formato `.lm`, `lumina.toml`
- `internals/` — pipeline (lexer → parser → semântica → codegen → runtime)
- `engineering/` — benchmarks, bugs, testes, ADRs