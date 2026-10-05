
## Resultados

C compiler: `clang`

### fib

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./fib_c 35 | 32.91 | 30.58 | 36.27 | 17.3% | 🟡 |
| ./fib_rs 35 | 32.08 | 29.60 | 35.66 | 18.9% | 🟡 |
| ./fib_go 35 | 62.17 | 59.22 | 79.28 | 32.3% | ⚠️ ruidoso |
| ./fib_lumina 35 | 31.85 | 26.50 | 45.52 | 59.7% | ⚠️ ruidoso |

### primes

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./primes_c 10000000 | 21.83 | 20.31 | 25.46 | 23.6% | ⚠️ ruidoso |
| ./primes_rs 10000000 | 21.68 | 20.69 | 25.29 | 21.2% | ⚠️ ruidoso |
| ./primes_go 10000000 | 35.93 | 33.97 | 38.39 | 12.3% | 🟡 |
| ./primes_lumina 10000000 | 24.25 | 23.29 | 27.95 | 19.2% | 🟡 |

### loop

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./loop_c 100000000 | 88.10 | 87.52 | 92.76 | 5.9% | ✅ |
| ./loop_rs 100000000 | 96.82 | 96.11 | 99.95 | 4.0% | ✅ |
| ./loop_go 100000000 | 82.55 | 82.10 | 84.70 | 3.2% | ✅ |
| ./loop_lumina 100000000 | 88.87 | 88.00 | 93.88 | 6.6% | ✅ |

### matrix

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./matrix_c 200 | 5.54 | 5.45 | 6.08 | 11.4% | 🟡 |
| ./matrix_i64_c 200 | 5.56 | 5.45 | 6.25 | 14.4% | 🟡 |
| ./matrix_rs 200 | 7.99 | 7.95 | 8.33 | 4.7% | ✅ |
| ./matrix_go 200 | 14.25 | 14.15 | 15.45 | 9.1% | ✅ |
| ./matrix_lumina 200 | 5.39 | 5.35 | 5.43 | 1.4% | ✅ |

### alloc_churn

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./alloc_churn_c 1000000 | 13.27 | 12.04 | 16.04 | 30.2% | ⚠️ ruidoso |
| ./alloc_churn_lumina 1000000 | 50.01 | 46.22 | 51.47 | 10.5% | 🟡 |
| ./alloc_churn_lumina_nogc 1000000 | 12.15 | 12.06 | 17.12 | 41.7% | ⚠️ ruidoso |

### primes: GC vs --no-gc

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./primes_lumina 10000000 | 27.79 | 25.23 | 35.24 | 36.0% | ⚠️ ruidoso |
| ./primes_lumina_nogc 10000000 | 23.48 | 22.90 | 29.45 | 27.9% | ⚠️ ruidoso |
