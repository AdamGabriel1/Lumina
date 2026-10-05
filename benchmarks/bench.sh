#!/usr/bin/env bash
# benchmarks/bench.sh — build + verify + measure
#
# Uso:
#   RUNS=20 WARMUP=3 CORE=1 ./bench.sh
#   CC=gcc ./bench.sh          # comparação cross-compiler (não-alinhada)
#
# Mudanças desta versão (v4):
#   - `bench_runtime` removido dos loops de build. Ele existe em
#     benchmarks/ como smoke test, mas nunca foi medido pelo hyperfine
#     (não está em CMDS) — compilar era trabalho desperdiçado.
#   - C compilado com clang (mesmo backend do Lumina). Alinha a comparação:
#     mede a linguagem + codegen, não "clang vs gcc". Override com CC=gcc.
#   - Adiciona `matrix_i64_c` (índices i64 puros, sem cast size_t).
#     Controla o efeito de vetorização que o gcc perde com `(size_t)i * n + k`.
#   - `alloc_churn.c` deve usar `bb()` (barreira asm) — ver comentário no arquivo.
#   - `alloc_churn.lm` deve usar `black_box(p as int)` — idem.
#   - Mantém `-fwrapv` (belt-and-suspenders: signed overflow é wrapping).
#   - Mantém as variantes --no-gc para primes e alloc_churn.
set -euo pipefail
cd "$(dirname "$0")"

CORE="${CORE:-1}"
RUNS="${RUNS:-20}"
WARMUP="${WARMUP:-3}"
DATE="$(date +%Y-%m-%d)"
OUT="results/${DATE}-codespace"
CC="${CC:-clang}"              # C alinhado com o backend do Lumina
mkdir -p "$OUT"

# ------------------------------------------------------------------ ambiente
{
  echo "# Benchmark run — $DATE"
  echo
  echo "## Ambiente"
  echo '```'
  neofetch 2>/dev/null || lscpu | head -25
  echo '```'
  echo
  echo "## Toolchains"
  echo '```'
  echo "C compiler: $CC ($($CC --version | head -1))"
  rustc --version
  go version
  node --version 2>/dev/null || true
  python3 --version
  echo "Lumina: $(cd .. && python3 -c 'import lumina_cli; print(lumina_cli.__version__)' 2>/dev/null || echo 'HEAD')"
  echo '```'
  echo
  echo "## Governor vCPU ${CORE} (antes)"
  echo '```'
  cat /sys/devices/system/cpu/cpu${CORE}/cpufreq/scaling_cur_freq 2>/dev/null || echo "n/a"
  echo '```'
} | tee "$OUT/env.md"

# ------------------------------------------------------------------ build
echo "==> compilando (C compiler: $CC)"

CFLAGS="-O3 -march=native -fwrapv"   # -fwrapv força overflow assinado a wrapping
for s in fib loop matrix primes alloc_churn; do
  $CC $CFLAGS "${s}.c" -o "${s}_c"
done

# Variante de matrix com índices i64 puros (sem cast size_t).
# Isola o efeito de vetorização: se `matrix_c` não vetoriza mas
# `matrix_i64_c` sim, o cast `(size_t)i * n + k` é o culpado.
if [ -f matrix_i64.c ]; then
  $CC $CFLAGS matrix_i64.c -o matrix_i64_c
fi

$CC $CFLAGS fib.cpp  -o fib_cpp 2>/dev/null || true
$CC $CFLAGS loop.cpp -o loop_cpp 2>/dev/null || true

RFLAGS="-C opt-level=3 -C target-cpu=native -C lto=fat -C codegen-units=1"
for s in fib loop matrix primes; do
  rustc $RFLAGS "${s}.rs" -o "${s}_rs"
done

for s in fib loop matrix primes; do
  go build -o "${s}_go" "${s}.go"
done

# PATCH (v4): `bench_runtime` removido do loop. Ele não é medido pelo
# hyperfine (não está em CMDS) e não entra na verificação de corretude.
# Compilar era trabalho desperdiçado. Ele continua disponível em
# benchmarks/bench_runtime.{c,lm} para smoke test manual.
for s in fib loop matrix primes alloc_churn; do
  lumina build "${s}.lm" --release
  mv -f "${s}" "${s}_lumina"
done

# Variantes sem GC para isolar custo do Boehm GC.
lumina build primes.lm --release --no-gc
mv -f primes primes_lumina_nogc

lumina build alloc_churn.lm --release --no-gc
mv -f alloc_churn alloc_churn_lumina_nogc

# ------------------------------------------------------------------ corretude
echo "==> verificando corretude"

declare -A ARGS=(
  [fib]=35
  [primes]=10000000
  [loop]=100000000
  [matrix]=200
  [alloc_churn]=1000000
)

fail=0
for suite in fib primes loop matrix alloc_churn; do
  N="${ARGS[$suite]}"
  ref=""
  ref_lang=""
  for lang in c rs go lumina; do
    bin="./${suite}_${lang}"
    [ -x "$bin" ] || continue
    raw="$(taskset -c "$CORE" "$bin" "$N" 2>/dev/null || true)"
    out="$(printf '%s' "$raw" | grep -oE '[0-9]+' | tail -1)"
    [ -z "$out" ] && out="__ERR__"
    if [ -z "$ref" ]; then
      ref="$out"; ref_lang="$lang"
      echo "  $suite: ref=\"$ref\"  (${suite}_${lang})"
    elif [ "$out" != "$ref" ]; then
      echo "  ❌ MISMATCH $suite/$lang  ref($ref_lang)=\"$ref\"  got=\"$out\""
      fail=1
    fi
  done
done
[ "$fail" -eq 0 ] || { echo "corretude FALHOU — abortando"; exit 1; }
echo "corretude OK"

# ------------------------------------------------------------------ hyperfine
if ! command -v hyperfine >/dev/null; then
  echo "==> instalando hyperfine"
  curl -sL https://github.com/sharkdp/hyperfine/releases/download/v1.18.0/hyperfine-v1.18.0-x86_64-unknown-linux-musl.tar.gz \
    | tar xz -C /tmp
  export PATH="/tmp/hyperfine-v1.18.0-x86_64-unknown-linux-musl:$PATH"
fi

echo "==> medindo (runs=$RUNS warmup=$WARMUP, pinned em vCPU $CORE)"

# Monta matriz de comandos. `matrix_i64_c` só entra se existir.
if [ -x ./matrix_i64_c ]; then
  MATRIX_CMDS="./matrix_c 200|./matrix_i64_c 200|./matrix_rs 200|./matrix_go 200|./matrix_lumina 200"
else
  MATRIX_CMDS="./matrix_c 200|./matrix_rs 200|./matrix_go 200|./matrix_lumina 200"
fi

declare -A CMDS=(
  [fib]="./fib_c 35|./fib_rs 35|./fib_go 35|./fib_lumina 35"
  [primes]="./primes_c 10000000|./primes_rs 10000000|./primes_go 10000000|./primes_lumina 10000000"
  [loop]="./loop_c 100000000|./loop_rs 100000000|./loop_go 100000000|./loop_lumina 100000000"
  [matrix]="${MATRIX_CMDS}"
  [alloc_churn]="./alloc_churn_c 1000000|./alloc_churn_lumina 1000000|./alloc_churn_lumina_nogc 1000000"
)

for suite in fib primes loop matrix alloc_churn; do
  echo "  → $suite"
  IFS='|' read -ra cmds <<< "${CMDS[$suite]}"
  taskset -c "$CORE" hyperfine \
    --warmup "$WARMUP" --runs "$RUNS" -N \
    --export-json "$OUT/${suite}.json" \
    "${cmds[@]}"
done

# ------------------------------------------------------------------ GC vs no-GC
echo "  → primes: GC vs --no-gc"
taskset -c "$CORE" hyperfine \
  --warmup "$WARMUP" --runs "$RUNS" -N \
  --export-json "$OUT/primes_gc_vs_nogc.json" \
  "./primes_lumina 10000000" \
  "./primes_lumina_nogc 10000000"

# ------------------------------------------------------------------ sumário
echo "==> sumário (mediana + IQR)"

{
  echo
  echo "## Resultados"
  echo
  echo "C compiler: \`$CC\`"
  for suite in fib primes loop matrix alloc_churn; do
    echo
    echo "### $suite"
    echo
    echo "| command | median (ms) | p25 | p75 | IQR/median | flag |"
    echo "|---|---:|---:|---:|---:|---|"
    jq -r '.results[] |
      (.times | sort) as $t |
      ($t | length) as $n |
      [$t[($n/4|floor)], $t[(3*$n/4|floor)]] as $q |
      [.command,
       (.median*1000),
       ($q[0]*1000),
       ($q[1]*1000),
       ((($q[1]-$q[0])/.median)*100)] | @tsv' \
      "$OUT/${suite}.json" \
    | awk -F'\t' '{
        flag = ($5 > 20) ? "⚠️ ruidoso" : (($5 > 10) ? "🟡" : "✅");
        printf "| %s | %.2f | %.2f | %.2f | %.1f%% | %s |\n", $1,$2,$3,$4,$5,flag
      }'
  done

  # ---- Bloco GC vs no-GC (primes) ----
  echo
  echo "### primes: GC vs --no-gc"
  echo
  echo "| command | median (ms) | p25 | p75 | IQR/median | flag |"
  echo "|---|---:|---:|---:|---:|---|"
  jq -r '.results[] |
    (.times | sort) as $t |
    ($t | length) as $n |
    [$t[($n/4|floor)], $t[(3*$n/4|floor)]] as $q |
    [.command,
     (.median*1000),
     ($q[0]*1000),
     ($q[1]*1000),
     ((($q[1]-$q[0])/.median)*100)] | @tsv' \
    "$OUT/primes_gc_vs_nogc.json" \
  | awk -F'\t' '{
      flag = ($5 > 20) ? "⚠️ ruidoso" : (($5 > 10) ? "🟡" : "✅");
      printf "| %s | %.2f | %.2f | %.2f | %.1f%% | %s |\n", $1,$2,$3,$4,$5,flag
    }'
} | tee "$OUT/summary.md"

echo
echo "OK — resultados em $OUT/"