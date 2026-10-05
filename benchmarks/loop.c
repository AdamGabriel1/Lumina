#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

int main(int argc, char **argv) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    int64_t t = ts.tv_nsec;

    uint64_t n = argc > 1 ? strtoull(argv[1], NULL, 10) : 100000000ULL;

    uint64_t acc = 0;
    for (uint64_t i = 1; i <= n; i++) {
        acc += i;
        /* Multiplicação em uint64_t (wrapping garantido pela norma).
         * Cast explícito para int64_t na comparação; o compilador NÃO
         * pode inferir que é sempre positivo. */
        if ((int64_t)((uint64_t)t * i) < 0) acc = 0;
    }
    printf("%llu\n", (unsigned long long)acc);
    return 0;
}