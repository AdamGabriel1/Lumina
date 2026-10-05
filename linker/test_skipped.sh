#!/usr/bin/env bash
# linker/test_skipped.sh — testa cada exemplo da skip list
# em todos os estágios (compile → clang -c → lumina-ld → run).
#
# Uso: ./linker/test_skipped.sh [dir]
#
# Saída: tabela com o estágio onde cada exemplo falha (ou OK).
# Serve para podar a skip list de `triagem.sh` com dados.

set -u
cd "$(dirname "$0")/.."

DIR="${1:-examples}"
TMP="/tmp/test_skipped"
mkdir -p "$TMP"

# A lista abaixo reflete o SKIP_LIST de triagem.sh.
# Se algo aqui passa, pode ser removido da skip list de triagem.sh.
SKIPPED=(
    util threads engine ffi_test wasm_js_interop
    api app async_server http_framework serve server proxy
    bootstrap_lexer database gc_test json_parser
    chip8 coroutines
)

# Cores (respeitam NO_COLOR)
if [ -z "${NO_COLOR:-}" ] && [ -t 1 ]; then
    G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; B=$'\033[1m'; N=$'\033[0m'
else
    G=; Y=; R=; B=; N=
fi

printf "%-24s %-14s %s\n" "EXEMPLO" "ESTÁGIO" "DETALHE"
printf "%-24s %-14s %s\n" "-------" "-------" "-------"

declare -A RESULTS

for name in "${SKIPPED[@]}"; do
    f="$DIR/$name.lm"
    [ -f "$f" ] || { 
        printf "%-24s %-14s %s\n" "$name" "${Y}(ausente)${N}" "arquivo não existe"
        RESULTS["$name"]="ausente"
        continue
    }

    ll="$TMP/$name.ll"
    o="$TMP/$name.o"
    exe="$TMP/$name"

    rm -f "$ll" "$o" "$exe"

    # 1) .lm → .ll
    python3 - <<PY >"$TMP/$name.ll.out" 2>"$TMP/$name.ll.err"
from lumina_cli.compiler.pipeline import compile_lumina
try:
    compile_lumina("$f", output_file="$ll", is_no_gc=True)
except SystemExit as e:
    raise SystemExit(e.code if e.code is not None else 1)
PY

    if [ ! -s "$ll" ]; then
        msg=$(tail -1 "$TMP/$name.ll.err" 2>/dev/null || echo "?")
        printf "%-24s %-14s %s\n" "$name" "${R}FAIL-COMPILE${N}" "$msg"
        RESULTS["$name"]="fail-compile"
        continue
    fi

    # 2) .ll → .o
    if ! clang -c -O2 -Wno-override-module -fno-pic -fno-pie \
              -fno-stack-protector "$ll" -o "$o" 2>"$TMP/$name.o.err"; then
        msg=$(tail -1 "$TMP/$name.o.err")
        printf "%-24s %-14s %s\n" "$name" "${R}FAIL-ASM${N}" "$msg"
        RESULTS["$name"]="fail-asm"
        continue
    fi

    # 3) link com lumina-ld
    if ! ./linker/lumina-ld linker/runtime/start.o "$o" linker/runtime/rt.o \
         -o "$exe" 2>"$TMP/$name.link.err"; then
        syms=$(grep -o "undefined reference to '[^']*'" "$TMP/$name.link.err" \
               | sed "s/.*'\(.*\)'/\1/" | sort -u | tr '\n' ' ')
        if [ -n "$syms" ]; then
            printf "%-24s %-14s %s\n" "$name" "${R}FAIL-LINK${N}" "UND: $syms"
        else
            msg=$(tail -1 "$TMP/$name.link.err")
            printf "%-24s %-14s %s\n" "$name" "${R}FAIL-LINK${N}" "$msg"
        fi
        RESULTS["$name"]="fail-link"
        continue
    fi

    # 4) run — silencia "Segmentation fault" do shell; o exit code captura tudo
    ( ulimit -c 0; timeout 5 "$exe" >"$TMP/$name.run.out" 2>&1 ) 2>/dev/null
    rc=$?
    if [ $rc -eq 124 ]; then
        printf "%-24s %-14s %s\n" "$name" "${Y}TIMEOUT${N}" "não terminou em 5s"
        RESULTS["$name"]="timeout"
    elif [ $rc -eq 139 ]; then
        msg=$(tail -1 "$TMP/$name.run.out" | head -c 60)
        printf "%-24s %-14s %s\n" "$name" "${R}SIGSEGV${N}" "exit=139 | $msg"
        RESULTS["$name"]="fail-run"
    elif [ $rc -ne 0 ]; then
        msg=$(tail -1 "$TMP/$name.run.out" | head -c 60)
        printf "%-24s %-14s %s\n" "$name" "${Y}FAIL-RUN${N}" "exit=$rc | $msg"
        RESULTS["$name"]="fail-run"
    else
        printf "%-24s %-14s %s\n" "$name" "${G}PASS${N}" ""
        RESULTS["$name"]="pass"
    fi
done

echo
echo "============================================================"
echo "  Resumo"
echo "============================================================"

# Conta por categoria
declare -A COUNTS
for name in "${!RESULTS[@]}"; do
    cat="${RESULTS[$name]}"
    COUNTS[$cat]=$(( ${COUNTS[$cat]:-0} + 1 ))
done

for cat in pass fail-compile fail-asm fail-link fail-run timeout ausente; do
    n=${COUNTS[$cat]:-0}
    [ "$n" -eq 0 ] && continue
    case "$cat" in
        pass)         printf "  ${G}%2d PASS${N}          — remova da skip list\n" "$n" ;;
        ausente)      printf "  %2d ausente       — arquivo não existe\n" "$n" ;;
        fail-compile) printf "  ${R}%2d fail-compile${N}  — bug do compilador\n" "$n" ;;
        fail-asm)     printf "  ${R}%2d fail-asm${N}      — bug do codegen (clang -c)\n" "$n" ;;
        fail-link)    printf "  ${R}%2d fail-link${N}     — símbolo faltando no rt.c ou bug do linker\n" "$n" ;;
        fail-run)     printf "  ${R}%2d fail-run${N}      — bug do programa ou runtime\n" "$n" ;;
        timeout)      printf "  ${Y}%2d timeout${N}       — loop infinito / servidor\n" "$n" ;;
    esac
done

echo
echo "Lista pronta para colar em triagem.sh (só os que ainda falham):"
echo
{
    for name in "${SKIPPED[@]}"; do
        cat="${RESULTS[$name]:-ausente}"
        [ "$cat" = "pass" ] && continue
        printf "%s " "$name"
    done
    echo
} | fold -s -w 74 | sed 's/^/  /'
echo
