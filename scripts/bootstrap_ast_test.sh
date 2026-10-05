#!/usr/bin/env bash
# Compara a AST do parser self-hosted com o parser Python.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

BIN="./lumina_core/parser"
if [ ! -x "$BIN" ]; then
    echo "erro: $BIN não existe. Rode 'lumina build lumina_core/parser.lm --release'"
    exit 1
fi

FIXTURES="${1:-tests/fixtures}"
FILES=$(find "$FIXTURES" -name '*.lm' | sort)

PASS=0
FAIL=0
FAILED_FILES=()

for f in $FILES; do
    name=$(basename "$f")

    lumina_out=$(timeout 10 "$BIN" "$f" 2>&1 || true)
    python_out=$(timeout 10 python3 scripts/dump_ast.py "$f" 2>&1 || true)

    if [ "$lumina_out" = "$python_out" ]; then
        echo "  ✅ $name"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $name"
        diff <(echo "$python_out") <(echo "$lumina_out") 2>/dev/null | head -20 | sed 's/^/     /' || true
        FAIL=$((FAIL + 1))
        FAILED_FILES+=("$name")
    fi
done

echo
echo "============================================================"
echo "AST equivalence: $PASS PASS / $FAIL FAIL"
echo "============================================================"

if [ "$FAIL" -gt 0 ]; then
    echo "Falharam:"
    for x in "${FAILED_FILES[@]}"; do
        echo "  · $x"
    done
    exit 1
fi