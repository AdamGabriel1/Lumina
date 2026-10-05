#include <stdio.h>
#include <assert.h>
#include <time.h>

int somar(int a, int b) { return a + b; }
int dividir(int a, int b) { if (b == 0) return 0; return a / b; }

void test_somar_1() { assert(somar(2, 2) == 4); }
void test_somar_2() { assert(somar(10, 50) == 60); }
void test_dividir_1() { assert(dividir(10, 2) == 5); }
void test_dividir_2() { assert(dividir(10, 0) == 0); }
void test_loop_pesado() {
    long long x = 0;
    for (int i = 0; i < 1000000; i++) x += i;
    assert(x == 499999500000);
}

int main() {
    clock_t start = clock();
    
    test_somar_1();
    test_somar_2();
    test_dividir_1();
    test_dividir_2();
    test_loop_pesado();
    
    clock_t end = clock();
    double time_spent = (double)(end - start) / CLOCKS_PER_SEC;
    printf("C Runtime: %.6f segundos\n", time_spent);
    return 0;
}
