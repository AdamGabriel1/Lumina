#!/usr/bin/env bash
# linker/test.sh — pipeline manual: .lm → .ll → .o → executável
#
# Uso: ./linker/test.sh [arquivo.lm] [saida_sem_ext]
#   padrão: tests/fixtures/hello_world.lm  →  /tmp/hw

set -euo pipefail

cd "$(dirname "$0")/.."

SRC="${1:-tests/fixtures/hello_world.lm}"
OUT="${2:-/tmp/hw}"

if [ ! -f "$SRC" ]; then
    echo "erro: arquivo não existe: $SRC" >&2
    exit 1
fi
if [ ! -x "./linker/lumina-ld" ]; then
    echo "erro: linker/lumina-ld não existe — rode 'make' em linker/ antes" >&2
    exit 1
fi

echo "==> 1. .lm → .ll"
python3 - <<PY
from lumina_cli.compiler.pipeline import compile_lumina
compile_lumina("$SRC", output_file="$OUT.ll", is_no_gc=True)
PY

echo "==> 2. .ll → .o (não-PIC)"
clang -c -O2 -Wno-override-module \
      -fno-pic -fno-pie -fno-stack-protector \
      "$OUT.ll" -o "$OUT.o"

echo "==> 3. link"
./linker/lumina-ld \
    linker/runtime/start.o \
    "$OUT.o" \
    linker/runtime/rt.o \
    -o "$OUT"

echo "==> 4. run"
echo "--- saída do programa ---"
set +e
"$OUT"
RC=$?
set -e
echo "--- fim (exit=$RC) ---"

echo "==> 5. inspect"
readelf -h "$OUT" | grep -E "Type|Entry|Machine"