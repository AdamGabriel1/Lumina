/* matrix_i64.c — mesma lógica de matrix.c, mas com índices i64 puros.
 * O cast `(size_t)i * n + k` em matrix.c impede o gcc de vetorizar.
 * Aqui tudo é i64, alinhado com o `matrix.lm`. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

int main(int argc, char **argv) {
    int64_t n = argc > 1 ? atoll(argv[1]) : 200;
    int64_t size = n * n;

    int64_t *a = malloc((size_t)size * 8);
    int64_t *b = malloc((size_t)size * 8);
    int64_t *c = malloc((size_t)size * 8);
    if (!a || !b || !c) return 1;

    for (int64_t i = 0; i < size; i++) {
        a[i] = i % 10;
        b[i] = (i * 2) % 10;
        c[i] = 0;
    }

    for (int64_t i = 0; i < n; i++)
        for (int64_t j = 0; j < n; j++) {
            int64_t s = 0;
            for (int64_t k = 0; k < n; k++)
                s += a[i * n + k] * b[k * n + j];
            c[i * n + j] = s;
        }

    int64_t total = 0;
    for (int64_t i = 0; i < size; i++) total += c[i];

    printf("%lld\n", (long long)total);
    free(a); free(b); free(c);
    return 0;
}
