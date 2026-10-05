#!/usr/bin/env bash
# =========================================================
# Compila todos os exemplos em examples/*.lm.
#
# Uso:
#   ./scripts/check_examples.sh                    # só compila (clang)
#   ./scripts/check_examples.sh --run              # compila + executa
#   ./scripts/check_examples.sh --run-only         # só executa
#   ./scripts/check_examples.sh --linker=self      # usa lumina-ld
#   ./scripts/check_examples.sh --run --linker=self
#   ./scripts/check_examples.sh --run -j4          # 4 workers
#   ./scripts/check_examples.sh --run -j 4         # idem (com espaço)
#   ./scripts/check_examples.sh --run -j "$(nproc)"
#   ./scripts/check_examples.sh --run --jobs=8
# =========================================================

set -u

RUN_MODE=0
RUN_ONLY=0
LINKER_FLAG=""
JOBS=1

# ---- Parser de argumentos (aceita -j N e -jN) ----
while [ $# -gt 0 ]; do
    case "$1" in
        --run)          RUN_MODE=1 ;;
        --run-only)     RUN_MODE=1; RUN_ONLY=1 ;;
        --linker=self)  LINKER_FLAG="--linker=self" ;;
        --linker=clang) LINKER_FLAG="" ;;
        -j|--jobs)
            if [ $# -lt 2 ]; then
                echo "erro: $1 requer um valor (ex: -j 4)" >&2
                exit 2
            fi
            JOBS="$2"
            shift
            ;;
        -j*)            JOBS="${1#-j}" ;;
        --jobs=*)       JOBS="${1#--jobs=}" ;;
        *)
            echo "aviso: argumento desconhecido: $1" >&2
            ;;
    esac
    shift
done

# Sanitiza JOBS: se vazio ou não-numérico, cai para 1
case "$JOBS" in
    ''|*[!0-9]*) JOBS=1 ;;
esac
[ "$JOBS" -lt 1 ] && JOBS=1

SKIP_FILE="tests/features/skip.txt"

# Skips específicos do modo --run
declare -A RUN_SKIP_MAP
if [ -f "tests/features/run_skip.txt" ] && [ "$RUN_MODE" = "1" ]; then
    while IFS= read -r line; do
        [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
        name=$(echo "$line" | awk '{print $1}')
        RUN_SKIP_MAP["$name"]=1
    done < "tests/features/run_skip.txt"
fi

PASS=0
SKIP=0
FAIL=0
FAILED_FILES=()

# Lê a skip list
declare -A SKIP_MAP
if [ -f "$SKIP_FILE" ]; then
    while IFS= read -r line; do
        [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
        name=$(echo "$line" | awk '{print $1}')
        SKIP_MAP["$name"]=1
    done < "$SKIP_FILE"
fi

# ---------- Worker ----------
# Protocolo: "<KIND>|<base>|<detalhe>"
run_one_example() {
    local f="$1"
    local base
    base=$(basename "$f")

    if [ "$RUN_ONLY" = "0" ]; then
        local output
        output=$(timeout 20 python3 -u -m lumina_cli build "$f" $LINKER_FLAG 2>&1)
        if ! echo "$output" | grep -q "Build concluído"; then
            local detail
            detail=$(echo "$output" | tail -3 | tr '\n' ' ')
            echo "FAIL-COMPILE|$base|$detail"
            return
        fi
    fi

    if [ "$RUN_MODE" = "1" ]; then
        local exe="examples/${base%.lm}"
        if [ ! -x "$exe" ]; then
            echo "FAIL-RUN|$base|(binário não encontrado: $exe)"
            return
        fi

        local expected_file="examples/${base%.lm}.expected"
        if [ -f "$expected_file" ]; then
            local actual expected
            actual=$(timeout 10 "$exe" 2>&1)
            expected=$(cat "$expected_file")
            if [ "$actual" = "$expected" ]; then
                echo "PASS-RUN|$base|"
            else
                echo "FAIL-RUN|$base|(output mismatch)"
            fi
        else
            if timeout 10 "$exe" > /dev/null 2>&1; then
                echo "PASS-RUN|$base|"
            else
                local rc=$?
                echo "FAIL-RUN|$base|(exit code: $rc)"
            fi
        fi
    else
        echo "PASS|$base|"
    fi
}

# ---------- Cabeçalho ----------
echo "============================================================"
echo "  check_examples.sh"
echo "  modo: $([ "$RUN_MODE" = "1" ] && echo "run" || echo "compile")"
echo "  linker: ${LINKER_FLAG:-clang (default)}"
echo "  jobs: $JOBS"
echo "============================================================"
echo

# ---------- Filtra skips ----------
FILES_TO_RUN=()
for f in examples/*.lm; do
    [ -f "$f" ] || continue
    base=$(basename "$f")

    if [ -n "${SKIP_MAP[$base]:-}" ]; then
        echo "⏭️  SKIP: $base"
        SKIP=$((SKIP + 1))
        continue
    fi

    if [ "$RUN_MODE" = "1" ] && [ -n "${RUN_SKIP_MAP[$base]:-}" ]; then
        echo "⏭️  SKIP (run): $base"
        SKIP=$((SKIP + 1))
        continue
    fi

    FILES_TO_RUN+=("$f")
done

# ---------- Executa ----------
export -f run_one_example
export RUN_MODE RUN_ONLY LINKER_FLAG

RAW=()
if [ ${#FILES_TO_RUN[@]} -gt 0 ]; then
    mapfile -t RAW < <(
        printf '%s\0' "${FILES_TO_RUN[@]}" \
        | xargs -0 -P "$JOBS" -I{} bash -c 'run_one_example "$@"' _ {}
    )
fi

# Nada rodou mas havia alvos → erro real (ex: xargs falhou)
if [ ${#FILES_TO_RUN[@]} -gt 0 ] && [ ${#RAW[@]} -eq 0 ]; then
    echo "erro: nenhum worker produziu saída" >&2
    exit 3
fi

# ---------- Agrega ----------
for line in "${RAW[@]}"; do
    [ -n "$line" ] || continue
    kind="${line%%|*}"
    rest="${line#*|}"
    name="${rest%%|*}"
    detail="${rest#*|}"

    case "$kind" in
        PASS)
            echo "✅ PASS: $name"
            PASS=$((PASS + 1))
            ;;
        PASS-RUN)
            echo "✅ PASS (ran): $name"
            PASS=$((PASS + 1))
            ;;
        FAIL-COMPILE)
            echo "❌ FAIL (compile): $name"
            [ -n "$detail" ] && echo "     $detail"
            FAIL=$((FAIL + 1))
            FAILED_FILES+=("$name")
            ;;
        FAIL-RUN)
            echo "❌ FAIL (run): $name"
            [ -n "$detail" ] && echo "     $detail"
            FAIL=$((FAIL + 1))
            FAILED_FILES+=("$name")
            ;;
        *)
            echo "?? linha desconhecida: $line"
            ;;
    esac
done

echo
echo "============================================================"
if [ "$RUN_MODE" = "1" ]; then
    echo "📊 PASS: $PASS    ⏭️  SKIP: $SKIP    ❌ FAIL: $FAIL  (modo: run${LINKER_FLAG:+, linker: self}, jobs: $JOBS)"
else
    echo "📊 PASS: $PASS    ⏭️  SKIP: $SKIP    ❌ FAIL: $FAIL  (modo: compile${LINKER_FLAG:+, linker: self}, jobs: $JOBS)"
fi
echo "============================================================"

if [ ${#FAILED_FILES[@]} -gt 0 ]; then
    echo
    echo "Falharam:"
    for f in "${FAILED_FILES[@]}"; do
        echo "  · $f"
    done
    exit 1
fi
exit 0