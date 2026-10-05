#!/bin/bash
# =========================================================
# Lumina Language Benchmark Suite
# =========================================================
# Uso:
#   ./scripts/run_benchmarks.sh           # Lumina com -O2 (padrão)
#   ./scripts/run_benchmarks.sh --release # Lumina com -O3
# =========================================================

set -u

LUMINA_FLAGS=""
for arg in "$@"; do
    if [ "$arg" = "--release" ]; then
        LUMINA_FLAGS="--release"
    fi
done

echo "========================================="
echo " 🚀 Lumina Language Benchmark Suite"
echo "========================================="
echo "Flags Lumina: ${LUMINA_FLAGS:-(padrão -O2)}"
echo

# ---------- Lumina ----------
echo "Compilando Lumina..."
for b in fib loop primes matrix; do
    rm -rf .lumina_cache
    if ! python3 -m lumina_cli build "benchmarks/${b}.lm" $LUMINA_FLAGS > /dev/null 2>&1; then
        echo "  ❌ Falha ao compilar benchmarks/${b}.lm"
    fi
done

# ---------- C ----------
echo "Compilando C (gcc -O2)..."
for b in fib loop primes matrix; do
    gcc -O2 -o "benchmarks/${b}_c" "benchmarks/${b}.c" 2>/dev/null
done

# ---------- C++ (só se existir) ----------
echo "Compilando C++ (g++ -O2)..."
for b in fib loop matrix; do
    src="benchmarks/${b}.cpp"
    if [ -f "$src" ]; then
        g++ -O2 -o "benchmarks/${b}_cpp" "$src" 2>/dev/null
    fi
done

# ---------- Rust (só se rustc existir) ----------
if command -v rustc > /dev/null 2>&1; then
    echo "Compilando Rust (rustc -O)..."
    for b in fib loop primes matrix; do
        src="benchmarks/${b}.rs"
        if [ -f "$src" ]; then
            rustc -O -o "benchmarks/${b}_rs" "$src" 2>/dev/null
        fi
    done
else
    echo "⚠️  rustc não encontrado — pulando Rust"
fi

# ---------- Go (só se go existir) ----------
if command -v go > /dev/null 2>&1; then
    echo "Compilando Go..."
    for b in fib loop primes matrix; do
        src="benchmarks/${b}.go"
        if [ -f "$src" ]; then
            go build -o "benchmarks/${b}_go" "$src" 2>/dev/null
        fi
    done
else
    echo "⚠️  go não encontrado — pulando Go"
fi

# ---------- Função de medição ----------
run_one() {
    local label="$1"
    local exe="$2"
    if [ ! -x "$exe" ]; then
        printf "  %-10s (não encontrado)\n" "$label"
        return
    fi
    start=$(date +%s.%N)
    "$exe" > /dev/null 2>&1
    end=$(date +%s.%N)
    printf "  %-10s %ss\n" "$label" "$(echo "$end - $start" | bc)"
}

run_node() {
    local label="Node.js"
    local src="$1"
    if [ ! -f "$src" ]; then
        printf "  %-10s (não encontrado)\n" "$label"
        return
    fi
    if ! command -v node > /dev/null 2>&1; then
        printf "  %-10s (node não instalado)\n" "$label"
        return
    fi
    start=$(date +%s.%N)
    node "$src" > /dev/null 2>&1
    end=$(date +%s.%N)
    printf "  %-10s %ss\n" "$label" "$(echo "$end - $start" | bc)"
}

run_py() {
    local label="Python"
    local src="$1"
    if [ ! -f "$src" ]; then
        printf "  %-10s (não encontrado)\n" "$label"
        return
    fi
    start=$(date +%s.%N)
    python3 "$src" > /dev/null 2>&1
    end=$(date +%s.%N)
    printf "  %-10s %ss\n" "$label" "$(echo "$end - $start" | bc)"
}

# ---------- Testes ----------
echo
echo "-----------------------------------------"
echo "Teste 1: Fibonacci Recursivo (N=35)"
echo "-----------------------------------------"
run_one "Lumina"  "./benchmarks/fib"
run_one "C"       "./benchmarks/fib_c"
run_one "Rust"    "./benchmarks/fib_rs"
run_one "Go"      "./benchmarks/fib_go"
run_node         "benchmarks/fib.js"
run_py           "benchmarks/fib.py"

echo
echo "-----------------------------------------"
echo "Teste 2: Loop Matemático (100M)"
echo "-----------------------------------------"
run_one "Lumina"  "./benchmarks/loop"
run_one "C"       "./benchmarks/loop_c"
run_one "Rust"    "./benchmarks/loop_rs"
run_one "Go"      "./benchmarks/loop_go"
run_node         "benchmarks/loop.js"

echo
echo "-----------------------------------------"
echo "Teste 3: Crivo de Eratóstenes (10M)"
echo "-----------------------------------------"
run_one "Lumina"  "./benchmarks/primes"
run_one "C"       "./benchmarks/primes_c"
run_one "Rust"    "./benchmarks/primes_rs"
run_one "Go"      "./benchmarks/primes_go"

echo
echo "-----------------------------------------"
echo "Teste 4: Multiplicação de Matrizes (200x200)"
echo "-----------------------------------------"
run_one "Lumina"  "./benchmarks/matrix"
run_one "C"       "./benchmarks/matrix_c"
run_one "Rust"    "./benchmarks/matrix_rs"
run_one "Go"      "./benchmarks/matrix_go"
run_node         "benchmarks/matrix.js"

echo
echo "========================================="
echo "Concluído."
echo "========================================="