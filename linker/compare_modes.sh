#!/usr/bin/env bash
# linker/compare_modes.sh — compara clang vs lumina-ld em todos os exemplos
set -u
cd "$(dirname "$0")/.."

DIR="${1:-examples}"
TMP="/tmp/compare_modes"
mkdir -p "$TMP"

declare -A CLANG_SELF
for f in "$DIR"/*.lm; do
    base=$(basename "$f" .lm)

    # modo clang
    if lumina build "$f" >/dev/null 2>&1; then
        CLANG_SELF[$base]="clang-ok"
    else
        CLANG_SELF[$base]="clang-fail"
    fi

    # modo self
    if lumina build "$f" --linker=self >/dev/null 2>&1; then
        CLANG_SELF[$base]="${CLANG_SELF[$base]}|self-ok"
    else
        CLANG_SELF[$base]="${CLANG_SELF[$base]}|self-fail"
    fi
done

echo "==> Resultados:"
divergencias=0
for base in $(printf '%s\n' "${!CLANG_SELF[@]}" | sort); do
    r="${CLANG_SELF[$base]}"
    if [ "$r" = "clang-ok|self-ok" ]; then
        printf "  OK        %s\n" "$base"
    elif [ "$r" = "clang-fail|self-fail" ]; then
        printf "  SKIP      %s\n" "$base"
    else
        printf "  DIVERGE   %-20s  %s\n" "$base" "$r"
        divergencias=$((divergencias + 1))
    fi
done

echo
echo "Divergências: $divergencias"
exit $([ $divergencias -eq 0 ] && echo 0 || echo 1)
