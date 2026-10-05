#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    long long limit = argc > 1 ? atoll(argv[1]) : 10000000LL;
    unsigned char *primes = malloc((size_t)limit);
    if (!primes) return 1;

    for (long long i = 0; i < limit; i++) primes[i] = 1;
    primes[0] = 0;
    if (limit > 1) primes[1] = 0;

    for (long long p = 2; p * p < limit; p++) {
        if (primes[p]) {
            for (long long i = p * p; i < limit; i += p)
                primes[i] = 0;
        }
    }

    long long count = 0;
    for (long long i = 0; i < limit; i++)
        if (primes[i]) count++;

    printf("%lld\n", count);
    free(primes);
    return 0;
}