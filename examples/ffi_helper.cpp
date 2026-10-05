#include <cstdio>

extern "C" void cpp_print_hello() {
    std::printf("Hello from C++\n");
}

extern "C" int cpp_multiply(int a, int b) {
    return a * b;
}
