#!/usr/bin/env bash
# linker/triagem.sh — roda todos os .lm de um diretório pelo pipeline
# do linker e acumula os símbolos que faltam na runtime.
#
# Uso: ./linker/triagem.sh [dir]   (padrão: examples)
#
# Variáveis de ambiente:
#   JOBS=N   paraleliza a triagem com N workers (default: nproc)
#
# A skip list fica em `linker/skip.txt`. Edite lá, não aqui.

set -u
cd "$(dirname "$0")/.."

DIR="${1:-examples}"
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 1)}"
case "$JOBS" in
    ''|*[!0-9]*) JOBS=1 ;;
esac
[ "$JOBS" -lt 1 ] && JOBS=1

TMP="/tmp/triagem"
rm -rf "$TMP"
mkdir -p "$TMP"

SKIP_FILE="linker/skip.txt"

declare -A SKIP_MAP
if [ -f "$SKIP_FILE" ]; then
    # `|| [ -n "$line" ]` garante que a última linha sem \n também
    # seja processada. Sem isso, um skip.txt sem newline final perde
    # a última entrada silenciosamente.
    while IFS= read -r line || [ -n "$line" ]; do
        [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
        name=$(echo "$line" | awk '{print $1}')
        SKIP_MAP["$name"]=1
    done < "$SKIP_FILE"
else
    echo "aviso: $SKIP_FILE não encontrado — rodando sem skip list" >&2
fi

PASS=()
FAIL_COMPILE=()
FAIL_LINK=()
FAIL_RUN=()
SKIP=()
MISSING_SYMS=()

# ---------- Worker ----------
# Protocolo: "<KIND>|<base>|<detalhe>"
run_one() {
    local f="$1"
    local base
    base=$(basename "$f" .lm)

    local sub="$TMP/$base"
    mkdir -p "$sub"
    local ll="$sub/$base.ll"
    local o="$sub/$base.o"
    local exe="$sub/$base"

    rm -f "$ll" "$o" "$exe"

    # 1) .lm → .ll
    python3 - <<PY >"$sub/ll.out" 2>"$sub/ll.err"
from lumina_cli.compiler.pipeline import compile_lumina
try:
    compile_lumina("$f", output_file="$ll", is_no_gc=True)
except SystemExit as e:
    raise SystemExit(e.code if e.code is not None else 1)
PY

    if [ ! -s "$ll" ]; then
        local msg
        msg=$(tail -1 "$sub/ll.err" 2>/dev/null || echo "?")
        echo "FAIL-COMPILE|$base|$msg"
        return
    fi

    # 2) .ll → .o
    if ! clang -c -O2 -Wno-override-module -fno-pic -fno-pie \
              -fno-stack-protector "$ll" -o "$o" 2>"$sub/o.err"; then
        local msg
        msg=$(tail -1 "$sub/o.err" 2>/dev/null || echo "?")
        echo "FAIL-ASM|$base|$msg"
        return
    fi

    # 3) link
    if ! ./linker/lumina-ld linker/runtime/start.o "$o" linker/runtime/rt.o \
         -o "$exe" 2>"$sub/link.err"; then
        local syms
        syms=$(grep -o "undefined reference to '[^']*'" "$sub/link.err" \
               | sed "s/.*'\(.*\)'/\1/" | sort -u | tr '\n' ' ')
        if [ -n "$syms" ]; then
            echo "FAIL-LINK|$base|$syms"
        else
            local msg
            msg=$(tail -1 "$sub/link.err" 2>/dev/null || echo "?")
            echo "FAIL-LINK|$base|$msg"
        fi
        return
    fi

    # 4) run
    timeout 5 "$exe" >"$sub/run.out" 2>&1
    local rc=$?
    if [ $rc -eq 124 ]; then
        echo "FAIL-RUN|$base|timeout"
    elif [ $rc -ne 0 ]; then
        echo "FAIL-RUN|$base|exit=$rc"
    else
        echo "OK|$base|"
    fi
}

export -f run_one
export TMP

# ---------- Filtra skips ----------
FILES_TO_RUN=()
for f in "$DIR"/*.lm; do
    [ -f "$f" ] || continue
    base=$(basename "$f" .lm)
    if [ -n "${SKIP_MAP[$base]:-}" ]; then
        printf "==> %-30s SKIP\n" "$base"
        SKIP+=("$base")
    else
        FILES_TO_RUN+=("$f")
    fi
done

# ---------- Executa ----------
RAW=()
if [ ${#FILES_TO_RUN[@]} -gt 0 ]; then
    mapfile -t RAW < <(
        printf '%s\0' "${FILES_TO_RUN[@]}" \
        | xargs -0 -P "$JOBS" -I{} bash -c 'run_one "$@"' _ {}
    )
fi

if [ ${#FILES_TO_RUN[@]} -gt 0 ] && [ ${#RAW[@]} -eq 0 ]; then
    echo "erro: nenhum worker produziu saída" >&2
    exit 3
fi

# ---------- Agrega ----------
for line in "${RAW[@]}"; do
    [ -n "$line" ] || continue
    kind="${line%%|*}"
    rest="${line#*|}"
    base="${rest%%|*}"
    detail="${rest#*|}"

    case "$kind" in
        OK)
            printf "==> %-30s OK\n" "$base"
            PASS+=("$base")
            ;;
        FAIL-COMPILE)
            printf "==> %-30s FAIL-COMPILE (%s)\n" "$base" "$detail"
            FAIL_COMPILE+=("$base")
            ;;
        FAIL-ASM)
            printf "==> %-30s FAIL-ASM (%s)\n" "$base" "$detail"
            FAIL_COMPILE+=("$base")
            ;;
        FAIL-LINK)
            printf "==> %-30s FAIL-LINK (%s)\n" "$base" "$detail"
            FAIL_LINK+=("$base")
            [ -n "$detail" ] && MISSING_SYMS+=($detail)
            ;;
        FAIL-RUN)
            printf "==> %-30s FAIL-RUN (%s)\n" "$base" "$detail"
            FAIL_RUN+=("$base")
            ;;
        *)
            echo "?? linha desconhecida: $line"
            ;;
    esac
done

echo
echo "============================================="
printf "PASS=%d  FAIL-COMPILE=%d  FAIL-LINK=%d  FAIL-RUN=%d  SKIP=%d  (jobs=%s)\n" \
    "${#PASS[@]}" "${#FAIL_COMPILE[@]}" "${#FAIL_LINK[@]}" "${#FAIL_RUN[@]}" "${#SKIP[@]}" "$JOBS"
echo "============================================="

if [ ${#MISSING_SYMS[@]} -gt 0 ]; then
    echo
    echo "Símbolos únicos que faltam na runtime:"
    printf '%s\n' "${MISSING_SYMS[@]}" | sort -u
fi

if [ ${#FAIL_COMPILE[@]} -gt 0 ]; then
    echo; echo "Falhas de compilação (bug do compilador, não do linker):"
    printf '  · %s\n' "${FAIL_COMPILE[@]}"
fi
if [ ${#FAIL_LINK[@]} -gt 0 ]; then
    echo; echo "Falhas de link (símbolo faltando ou bug do linker):"
    printf '  · %s\n' "${FAIL_LINK[@]}"
fi
if [ ${#FAIL_RUN[@]} -gt 0 ]; then
    echo; echo "Falhas de execução (bug do programa, codegen ou runtime):"
    printf '  · %s\n' "${FAIL_RUN[@]}"
fi
if [ ${#SKIP[@]} -gt 0 ]; then
    echo; echo "Pulados:"
    printf '  · %s\n' "${SKIP[@]}"
fi