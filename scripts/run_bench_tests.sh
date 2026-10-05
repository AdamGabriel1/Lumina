#!/bin/bash
echo "🏁 Iniciando Benchmark (10 Milhões de iterações - clang -O3)..."
echo "Compilando os binários..."

# Compila ambos em silêncio
clang -O3 benchmarks/bench_runtime.c -o benchmarks/bench_runtime_c > /dev/null 2>&1
lumina build benchmarks/bench_runtime.lm > /dev/null 2>&1

echo "Executando 10 vezes para calcular a média..."

c_times=()
lumina_times=()

for i in {1..10}; do
    # Roda C e extrai apenas o número do tempo
    c_out=$(./benchmarks/bench_runtime_c 10000000 | grep "C Runtime:" | awk '{print $3}')
    c_times+=($c_out)
    
    # Roda Lumina e extrai apenas o número do tempo
    l_out=$(./benchmarks/bench_runtime 10000000 | grep "Lumina Runtime:" | awk '{print $3}')
    lumina_times+=($l_out)
done

# Calcula a média usando awk
c_avg=$(echo "${c_times[*]}" | awk '{s=0; for(i=1;i<=NF;i++) s+=$i; print s/NF}')
l_avg=$(echo "${lumina_times[*]}" | awk '{s=0; for(i=1;i<=NF;i++) s+=$i; print s/NF}')

echo "================================================================"
echo "📊 Resultados Finais (Média de 10 execuções):"
echo "C Runtime Média:      $c_avg segundos"
echo "Lumina Runtime Média: $l_avg segundos"
echo "================================================================"

# Limpeza
rm -f benchmarks/bench_runtime_c benchmarks/bench_runtime