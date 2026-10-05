function fib(n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}
const n = process.argv[2] ? parseInt(process.argv[2], 10) : 35;
console.log(fib(n));