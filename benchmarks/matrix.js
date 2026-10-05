const n = process.argv[2] ? parseInt(process.argv[2], 10) : 200;
const size = n * n;

const a = new BigInt64Array(size);
const b = new BigInt64Array(size);
const c = new BigInt64Array(size);

for (let i = 0; i < size; i++) {
    a[i] = BigInt(i % 10);
    b[i] = BigInt((i * 2) % 10);
}

for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
        let s = 0n;
        for (let k = 0; k < n; k++) {
            s += a[i * n + k] * b[k * n + j];
        }
        c[i * n + j] = s;
    }
}

let total = 0n;
for (let i = 0; i < size; i++) total += c[i];
console.log(total.toString());