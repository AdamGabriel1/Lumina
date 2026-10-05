#include <stdio.h>
#include <stdlib.h>

/* Barreira idêntica ao `black_box` do Lumina. Impede que o LLVM
 * elimine pares malloc/free como dead code. */
static inline void bb(void *p) {
    __asm__ __volatile__("" : : "r"(p) : "memory");
}

int main(int argc, char **argv) {
    long long n = argc > 1 ? atoll(argv[1]) : 1000000;
    unsigned int seed = 12345u;

    long long total = 0;
    for (long long i = 0; i < n; i++) {
        seed = seed * 1103515245u + 12345u;
        int size = (int)((seed >> 16) % 512) + 1;

        char *p = malloc((size_t)size);
        if (p) {
            p[0] = (char)(i & 0xff);
            bb(p);                        /* ← barreira */
            total += p[0];
            free(p);
        }
    }
    printf("%lld\n", total);
    return 0;
}