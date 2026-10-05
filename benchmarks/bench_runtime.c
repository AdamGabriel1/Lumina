#include <stdio.h>
#include <stdlib.h>
#include <time.h>

long long somar(long long a, long long b) { return a + b; }
long long dividir(long long a, long long b) { if (b == 0) return 0; return a / b; }

int main(int argc, char **argv) {
    long long limit = 10000000;
    if (argc > 1) {
        limit = atoll(argv[1]);
    }

    clock_t start = clock();
    
    long long x = 0;
    for (long long i = 0; i < limit; i++) {
        x += i;
    }
    
    // Usamos o x para o compilador não otimizar a variável fora
    printf("Resultado: %lld\n", x);
    
    clock_t end = clock();
    double time_spent = (double)(end - start) / CLOCKS_PER_SEC;
    printf("C Runtime: %f segundos\n", time_spent);
    return 0;
}