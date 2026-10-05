#!/usr/bin/env bash
# scripts/update_test_badge.sh — roda pytest, atualiza badge do README.
#
# Uso:
#   ./scripts/update_test_badge.sh          # atualiza README.md
#   ./scripts/update_test_badge.sh --check  # só verifica (exit 1 se desatualizado)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

# Roda pytest e captura "N passed"
OUT=$(pytest tests/ -q 2>&1 | tail -5)
COUNT=$(echo "$OUT" | grep -oE '[0-9]+ passed' | head -1 | grep -oE '[0-9]+')

if [ -z "$COUNT" ]; then
    echo "erro: não consegui extrair a contagem de 'pytest tests/ -q'" >&2
    echo "$OUT" >&2
    exit 1
fi

echo "pytest: $COUNT passed"

# Arquivos que mencionam a contagem
FILES=("README.md" "docs/engineering/tests.md" "docs/contributing.md")

CHANGED=0
for f in "${FILES[@]}"; do
    [ -f "$f" ] || continue
    # Substitui padrões "NNN passed" e "NNN pytest" pela contagem atual.
    OLD=$(cat "$f")
    NEW=$(echo "$OLD" | sed -E "s/[0-9]+ passed/${COUNT} passed/g; s/tests-[0-9]+%20passed/tests-${COUNT}%20passed/g")
    if [ "$OLD" != "$NEW" ]; then
        if [ "$CHECK_ONLY" = "1" ]; then
            echo "  desatualizado: $f" >&2
            CHANGED=1
        else
            echo "$NEW" > "$f"
            echo "  atualizado: $f"
        fi
    fi
done

if [ "$CHECK_ONLY" = "1" ] && [ "$CHANGED" = "1" ]; then
    echo "erro: docs desatualizados. Rode sem --check para corrigir." >&2
    exit 1
fi
