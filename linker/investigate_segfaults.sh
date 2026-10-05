#!/usr/bin/env bash
# linker/investigate_segfaults.sh — gdb backtrace dos 3 segfaults
# Uso: ./linker/investigate_segfaults.sh [name1 name2 ...]
#      padrão: gc_test chip8 coroutines

set -u
cd "$(dirname "$0")/.."

NAMES=("$@")
[ ${#NAMES[@]} -eq 0 ] && NAMES=(gc_test chip8 coroutines)

if ! command -v gdb >/dev/null; then
    echo "aviso: gdb não encontrado. Instale com 'sudo apt install gdb'." >&2
    exit 1
fi

TMP="/tmp/investigate"
mkdir -p "$TMP"

for name in "${NAMES[@]}"; do
    f="examples/$name.lm"
    [ -f "$f" ] || { echo "== $name: arquivo não existe"; continue; }

    echo
    echo "============================================================"
    echo "  $name"
    echo "============================================================"

    # 1) .ll com debug info
    python3 - <<PY >"$TMP/$name.ll.out" 2>"$TMP/$name.ll.err"
from lumina_cli.compiler.pipeline import compile_lumina
try:
    compile_lumina("$f", output_file="$TMP/$name.ll", is_no_gc=True, is_debug=True)
except SystemExit as e:
    raise SystemExit(e.code if e.code is not None else 1)
PY

    if [ ! -s "$TMP/$name.ll" ]; then
        echo "  FAIL-COMPILE:"
        tail -5 "$TMP/$name.ll.err" | sed 's/^/    /'
        continue
    fi

    # 2) .o
    clang -c -O0 -g -Wno-override-module -fno-pic -fno-pie \
          -fno-stack-protector "$TMP/$name.ll" -o "$TMP/$name.o" 2>"$TMP/$name.o.err"
    if [ $? -ne 0 ]; then
        echo "  FAIL-ASM:"; tail -5 "$TMP/$name.o.err" | sed 's/^/    /'
        continue
    fi

    # 3) link
    ./linker/lumina-ld linker/runtime/start.o "$TMP/$name.o" \
        linker/runtime/rt.o -o "$TMP/$name" 2>"$TMP/$name.link.err" || {
        echo "  FAIL-LINK:"; tail -5 "$TMP/$name.link.err" | sed 's/^/    /'
        continue
    }

    # 4) gdb — captura crash
    gdb -batch \
        -ex "set pagination off" \
        -ex "run" \
        -ex "echo \n--- BACKTRACE ---\n" \
        -ex "bt" \
        -ex "echo \n--- REGISTERS ---\n" \
        -ex "info registers rip rsp rbp rdi rsi rax" \
        -ex "echo \n--- CODE at RIP ---\n" \
        -ex "x/8i \$rip-16" \
        "$TMP/$name" 2>&1 | grep -v "^$" | head -60 | sed 's/^/  /'
done
