---
status: aceito
---

# ADR 0001 — LLVM como backend

## Contexto
Precisávamos de um backend com otimizações maduras e portabilidade.

## Decisão
Emitir LLVM IR diretamente do codegen em Python (`lumina/codegen/`).

## Consequências
- ✅ Otimizações (TCO, inlining) de graça
- ⚠️ Dependência pesada (llvmlite)
- ⚠️ Debug de IR é mais difícil que bytecode próprio
