#include <cstdio>
#include <cstdlib>

static long long fib(long long n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}

int main(int argc, char **argv) {
    long long n = argc > 1 ? std::atoll(argv[1]) : 35;
    std::printf("%lld\n", fib(n));
    return 0;
}