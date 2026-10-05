const n = process.argv[2] ? parseInt(process.argv[2], 10) : 100000000;

let acc = 0;
for (let i = 1; i <= n; i++) {
    acc += i;
}
// Node não DCE esse tipo de loop, mas evita qualquer fold trivial:
if (acc === -1) console.log("unreachable");
console.log(acc);