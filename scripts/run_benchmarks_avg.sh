#!/bin/bash

# Função para calcular a média de 10 execuções
get_avg_time() {
    local cmd=$1
    local runs=10
    local total=0
    local i
    
    for i in $(seq 1 $runs); do
        start=$(date +%s.%N)
        $cmd > /dev/null
        end=$(date +%s.%N)
        dur=$(echo "$end - $start" | bc)
        total=$(echo "$total + $dur" | bc)
    done
    
    # Calcula a média com 4 casas decimais
    echo "scale=4; $total / $runs" | bc
}

echo "========================================="
echo " 🚀 Lumina Language Benchmark Suite (Média de 10 runs)"
echo "========================================="

# NOVO: Limpa todos os binários antigos para evitar cache
echo "Limpando binários antigos..."
rm -f benchmarks/fib benchmarks/loop benchmarks/primes benchmarks/matrix
rm -f benchmarks/fib_c benchmarks/loop_c benchmarks/primes_c benchmarks/matrix_c
rm -f benchmarks/fib_rs benchmarks/loop_rs benchmarks/primes_rs benchmarks/matrix_rs
rm -f benchmarks/fib_go benchmarks/loop_go benchmarks/primes_go benchmarks/matrix_go
rm -f benchmarks/fib_cpp benchmarks/loop_cpp benchmarks/primes_cpp benchmarks/matrix_cpp

# NOVO: Limpa o cache da Lumina
rm -rf .lumina_cache

echo "Compilando Lumina (O3 + Native CPU)..."
python3 lumina_cli.py build benchmarks/fib.lm
python3 lumina_cli.py build benchmarks/loop.lm
python3 lumina_cli.py build benchmarks/primes.lm
python3 lumina_cli.py build benchmarks/matrix.lm

echo "Compilando C (clang -O3)..."
clang -O3 -march=native -funroll-loops -o benchmarks/fib_c benchmarks/fib.c
clang -O3 -march=native -funroll-loops -o benchmarks/loop_c benchmarks/loop.c
clang -O3 -march=native -funroll-loops -o benchmarks/primes_c benchmarks/primes.c
clang -O3 -march=native -funroll-loops -o benchmarks/matrix_c benchmarks/matrix.c

echo "Compilando Rust (rustc -O)..."
rustc -O -o benchmarks/fib_rs benchmarks/fib.rs 2>/dev/null
rustc -O -o benchmarks/loop_rs benchmarks/loop.rs 2>/dev/null
rustc -O -o benchmarks/primes_rs benchmarks/primes.rs 2>/dev/null
rustc -O -o benchmarks/matrix_rs benchmarks/matrix.rs 2>/dev/null

echo "Compilando Go..."
go build -o benchmarks/fib_go benchmarks/fib.go
go build -o benchmarks/loop_go benchmarks/loop.go
go build -o benchmarks/primes_go benchmarks/primes.go
go build -o benchmarks/matrix_go benchmarks/matrix.go

echo ""
echo "Executando testes (isso pode levar alguns minutos)..."
echo ""

echo "-----------------------------------------"
echo "Teste 1: Fibonacci Recursivo (N=35)"
echo "-----------------------------------------"
echo -n "Lumina:   "; t=$(get_avg_time "./benchmarks/fib"); echo " ⏱  $t s"
echo -n "C:        "; t=$(get_avg_time "./benchmarks/fib_c"); echo " ⏱  $t s"
echo -n "Rust:     "; t=$(get_avg_time "./benchmarks/fib_rs"); echo " ⏱  $t s"
echo -n "Go:       "; t=$(get_avg_time "./benchmarks/fib_go"); echo " ⏱  $t s"
echo -n "Node.js:  "; t=$(get_avg_time "node benchmarks/fib.js"); echo " ⏱  $t s"
echo -n "Python:   "; t=$(get_avg_time "python3 benchmarks/fib.py"); echo " ⏱  $t s"

echo ""
echo "-----------------------------------------"
echo "Teste 2: Loop Matemático (100 Milhões)"
echo "-----------------------------------------"
echo -n "Lumina:   "; t=$(get_avg_time "./benchmarks/loop"); echo " ⏱  $t s"
echo -n "C:        "; t=$(get_avg_time "./benchmarks/loop_c"); echo " ⏱  $t s"
echo -n "Rust:     "; t=$(get_avg_time "./benchmarks/loop_rs"); echo " ⏱  $t s"
echo -n "Go:       "; t=$(get_avg_time "./benchmarks/loop_go"); echo " ⏱  $t s"
echo -n "Node.js:  "; t=$(get_avg_time "node benchmarks/loop.js"); echo " ⏱  $t s"

echo ""
echo "-----------------------------------------"
echo "Teste 3: Crivo de Eratóstenes (10 Milhões)"
echo "-----------------------------------------"
echo -n "Lumina:   "; t=$(get_avg_time "./benchmarks/primes"); echo " ⏱  $t s"
echo -n "C:        "; t=$(get_avg_time "./benchmarks/primes_c"); echo " ⏱  $t s"
echo -n "Rust:     "; t=$(get_avg_time "./benchmarks/primes_rs"); echo " ⏱  $t s"
echo -n "Go:       "; t=$(get_avg_time "./benchmarks/primes_go"); echo " ⏱  $t s"

echo ""
echo "-----------------------------------------"
echo "Teste 4: Multiplicação de Matrizes (200x200)"
echo "-----------------------------------------"
echo -n "Lumina:   "; t=$(get_avg_time "./benchmarks/matrix"); echo " ⏱  $t s"
echo -n "C:        "; t=$(get_avg_time "./benchmarks/matrix_c"); echo " ⏱  $t s"
echo -n "Rust:     "; t=$(get_avg_time "./benchmarks/matrix_rs"); echo " ⏱  $t s"
echo -n "Go:       "; t=$(get_avg_time "./benchmarks/matrix_go"); echo " ⏱  $t s"
echo -n "Node.js:  "; t=$(get_avg_time "node benchmarks/matrix.js"); echo " ⏱  $t s"

echo "========================================="
