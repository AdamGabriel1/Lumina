
## Resultados

C compiler: `clang`

### fib

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./fib_c 35 | 43.54 | 40.40 | 50.01 | 22.1% | ⚠️ ruidoso |
| ./fib_rs 35 | 44.07 | 42.03 | 51.07 | 20.5% | ⚠️ ruidoso |
| ./fib_go 35 | 84.79 | 77.49 | 87.11 | 11.3% | 🟡 |
| ./fib_lumina 35 | 40.40 | 38.19 | 43.63 | 13.4% | 🟡 |

### primes

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./primes_c 10000000 | 35.37 | 33.44 | 37.62 | 11.8% | 🟡 |
| ./primes_rs 10000000 | 35.89 | 35.06 | 38.16 | 8.7% | ✅ |
| ./primes_go 10000000 | 57.67 | 50.25 | 79.88 | 51.4% | ⚠️ ruidoso |
| ./primes_lumina 10000000 | 37.50 | 37.10 | 40.53 | 9.1% | ✅ |

### loop

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./loop_c 100000000 | 106.55 | 100.89 | 132.26 | 29.4% | ⚠️ ruidoso |
| ./loop_rs 100000000 | 151.38 | 139.03 | 183.26 | 29.2% | ⚠️ ruidoso |
| ./loop_go 100000000 | 99.87 | 97.55 | 107.12 | 9.6% | ✅ |
| ./loop_lumina 100000000 | 106.80 | 103.28 | 120.01 | 15.7% | 🟡 |

### matrix

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./matrix_c 200 | 7.94 | 7.84 | 8.84 | 12.6% | 🟡 |
| ./matrix_i64_c 200 | 7.71 | 7.40 | 7.80 | 5.3% | ✅ |
| ./matrix_rs 200 | 17.22 | 15.71 | 23.31 | 44.2% | ⚠️ ruidoso |
| ./matrix_go 200 | 17.23 | 16.94 | 23.51 | 38.1% | ⚠️ ruidoso |
| ./matrix_lumina 200 | 9.04 | 8.70 | 9.60 | 10.0% | ✅ |

### alloc_churn

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./alloc_churn_c 1000000 | 18.65 | 18.10 | 20.42 | 12.5% | 🟡 |
| ./alloc_churn_lumina 1000000 | 53.97 | 53.04 | 55.09 | 3.8% | ✅ |
| ./alloc_churn_lumina_nogc 1000000 | 20.14 | 19.91 | 20.54 | 3.1% | ✅ |

### primes: GC vs --no-gc

| command | median (ms) | p25 | p75 | IQR/median | flag |
|---|---:|---:|---:|---:|---|
| ./primes_lumina 10000000 | 39.23 | 38.67 | 46.50 | 20.0% | 🟡 |
| ./primes_lumina_nogc 10000000 | 40.50 | 37.43 | 52.79 | 37.9% | ⚠️ ruidoso |
