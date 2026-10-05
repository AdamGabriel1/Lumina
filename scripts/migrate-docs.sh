#!/usr/bin/env bash
# scripts/migrate-docs.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

mkdir -p site
git mv docs/index.html site/ 2>/dev/null || mv docs/index.html site/
git mv docs/index.json site/ 2>/dev/null || mv docs/index.json site/

mkdir -p docs/getting-started docs/guia docs/referencia \
         docs/internals docs/engineering/decisoes

git mv docs/guia-rapido.md   docs/getting-started/guia-rapido.md
git mv docs/linguagem.md     docs/guia/linguagem.md
git mv docs/stdlib.md        docs/guia/stdlib.md
git mv docs/ferramental.md   docs/guia/ferramental.md
git mv docs/internals.md     docs/internals/arquitetura.md

# ADRs: template vazio pra você preencher
cat > docs/engineering/decisoes/template.md <<'EOF'
---
status: proposto
data: AAAA-MM-DD
---

# ADR NNNN — Título

## Contexto
## Decisão
## Consequências
EOF

# Um ADR real pra começar
cat > docs/engineering/decisoes/0001-backend-llvm.md <<'EOF'
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
EOF

echo "✓ migração concluída. Revise com: git status && tree docs -L 3"
