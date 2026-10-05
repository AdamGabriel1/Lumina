#include <cstdio>
#include <cstdlib>
#include <cstdint>

int main(int argc, char **argv) {
    uint64_t n = argc > 1 ? std::strtoull(argv[1], nullptr, 10) : 100000000ULL;
    uint64_t acc = 0;
    for (uint64_t i = 1; i <= n; i++) {
        acc += i;
        asm volatile("" : "+r"(acc));   // barreira: impede Gauss-sum
    }
    std::printf("%llu\n", (unsigned long long)acc);
    return 0;
}