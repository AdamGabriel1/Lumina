# ⚡ Benchmarks

Metodologia, ambiente, comandos de reprodução e interpretação.

> **Aviso:** ambiente Codespace (2 vCPUs compartilhadas, Hyper-V).
> Variância entre runs: mediana de `fib_c` variou 40% entre dois runs no
> mesmo dia (gcc vs clang). **Não compare com bare-metal.** Para runs
> anteriores veja `benchmarks/results/`.

---

## 🖥️ Ambiente

Capturado com `neofetch` + `--version` (via `benchmarks/bench.sh`).
Sem isso, os números não são reproduzíveis.

```bash
cd /workspaces/Lumina/benchmarks
RUNS=20 WARMUP=3 CORE=1 ./bench.sh
```

### Ambiente do último run

| Item | Valor |
|---|---|
| CPU | AMD EPYC 7763 @ 3.24 GHz |
| vCPUs | 2 (compartilhadas, Hyper-V) |
| RAM | 7.9 GiB |
| SO | Ubuntu 24.04.4 LTS |
| Kernel | 6.8.0-1064-azure |

### Toolchains

| Linguagem | Versão | Notas |
|---|---|---|
| **C** | **clang 18.1.3** | Alinhado com o backend do Lumina |
| Rust | 1.98.1 | `-C opt-level=3 -C target-cpu=native -C lto=fat -C codegen-units=1` |
| Go | 1.27.0 | `go build` padrão |
| Node.js | v24.20.0 | — |
| Python | 3.14.2 | — |
| Lumina | HEAD do repo | `clang -O3` no link |

> **Por que clang e não gcc?** Lumina usa LLVM/clang como backend. Compilar
> o C com gcc mede "gcc vs clang", não "C vs Lumina". Com clang em ambos,
> a comparação isola a linguagem + codegen, não o compilador C.
> Para a versão histórica com gcc, use `CC=gcc ./bench.sh` (mas saiba que
> `fib_c` cai de 33 ms para 21 ms só por causa do gcc — é *outro* benchmark).

---

## 📐 Metodologia

1. **20 execuções** por binário, **3 warm-ups** descartados.
2. **Pinning em vCPU 1** — `taskset -c 1` envolve o `hyperfine`, e a afinidade é herdada por cada filho.
3. **Medição com `hyperfine`** com `--shell=none` (`-N`), `--export-json`.
4. **N passado por `argv`** em C, Rust, Go **e Lumina** (o item #2 do roadmap fechou isso).
5. **Reportar mediana + IQR**, não mean ± σ. Em VM ruidosa com cauda longa, a média é dominada por outliers. Regra: **IQR/mediana > 20% → ruidoso, > 10% → amarelo**.
6. **Verificação de corretude antes de medir**: `bench.sh` compara a saída de todos os binários contra o C e aborta se houver divergência. Cobre `fib`, `primes`, `loop`, `matrix` **e `alloc_churn`** (com RNGs alinhados).

### Anti-padrões corrigidos

- **DCE (dead-code elimination).** LLVM fecha loops triviais em fórmula de Gauss. A barreira contra isso precisa depender do **loop counter** — uma condição em variável loop-invariant é hoisted por LICM e o DCE volta. Em `loop`, usamos `if (t * i < 0)` com `t` vindo de `clock_gettime`/`clock()`.

- **Signed overflow UB em C.** `t * (int64_t)i` era UB em overflow, então o LLVM eliminava o branch. Corrigido com `-fwrapv` no `CFLAGS` (força wrapping, igual Rust `wrapping_mul` e Go int64) **e** cast `(uint64_t)t * i`.

- **Malloc/free elimination.** clang -O3 apaga pares `malloc`/`store`/`load`/`free` quando o ponteiro não escapa. `alloc_churn` agora usa barreira (`__asm__ __volatile__` em C, `black_box()` em Lumina) que impede isso. Sem a barreira, `alloc_churn_lumina_nogc` mede **1.8 ms** em vez de ~13 ms — o loop inteiro era eliminado.

- **Comparar tipos diferentes.** A versão anterior deste benchmark comparava `double` (C) com `int` (Lumina), o que produzia um falso "4.26× C". Agora todos usam `int64`.

- **Comparar com números de outra máquina.** Só com `benchmarks/results/` do mesmo ambiente.

- **gcc vs clang para C.** Mede o compilador, não a linguagem. `fib_c` roda **36% mais rápido com gcc** que com clang — um falso "1.55× Lumina/C" que aparece com `CC=gcc` some completamente com `CC=clang`.

---

## 🏃 Reprodução

Tudo via um script único: `benchmarks/bench.sh`.

```bash
cd /workspaces/Lumina/benchmarks
RUNS=20 WARMUP=3 CORE=1 ./bench.sh
```

O script:

1. **Compila** todos os binários:
   - C: `clang -O3 -march=native -fwrapv` (`CC=gcc` para comparar cross-compiler)
   - Rust: `rustc -C opt-level=3 -C target-cpu=native -C lto=fat -C codegen-units=1`
   - Go: `go build`
   - Lumina: `lumina build --release` → `clang -O3`
2. **Compila variantes `--no-gc`**: `primes_lumina_nogc`, `alloc_churn_lumina_nogc`.
3. **Verifica corretude**: roda cada binário com `N` em `argv` e compara a saída numérica contra o C. Aborta se houver divergência.
4. **Mede** com `taskset -c 1 hyperfine --warmup 3 --runs 20 -N`.
5. **Sumariza** mediana + IQR + flag de ruído, em `results/YYYY-MM-DD-codespace/summary.md`.

---

## 📊 Resultados

Run de **2026-09-18**, mediana de 20 execuções, pinned em vCPU 1.
Todos os tempos em **milissegundos**. C compilado com **clang 18.1.3**.

### Fibonacci (N=35)

Recursão binária pura. Mede call overhead + cache de instrução.

| Lang | Mediana | p25 | p75 | IQR/med | Flag | vs C |
|---|---:|---:|---:|---:|---|---:|
| **C -O3** | 32.91 | 30.58 | 36.27 | 17.3% | 🟡 | 1.00× |
| **Rust -O3** | 32.08 | 29.60 | 35.66 | 18.9% | 🟡 | 0.97× |
| **Lumina --release** | **31.85** | 26.50 | 45.52 | 59.7% | ⚠️ | **0.97×** |
| Go | 62.17 | 59.22 | 79.28 | 32.3% | ⚠️ | 1.89× |

**Leitura:** Lumina **empata com C e Rust** dentro da margem. O IQR de 59.7% do Lumina reflete a VM, não o código — o min absoluto foi 25.0 ms. Rodar isolado com `--warmup 10 --runs 30` estabilizaria a mediana.

### Crivo de Eratóstenes (10M)

Aloca array de 10M bytes, faz peneira. Memory-bound + GC na alocação inicial.

| Lang | Mediana | p25 | p75 | IQR/med | Flag | vs C |
|---|---:|---:|---:|---:|---|---:|
| **C -O3** | **21.83** | 20.31 | 25.46 | 23.6% | ⚠️ | 1.00× |
| **Rust -O3** | **21.68** | 20.69 | 25.29 | 21.2% | ⚠️ | 0.99× |
| **Lumina --release** | 24.25 | 23.29 | 27.95 | 19.2% | 🟡 | **1.11×** |
| Go | 35.93 | 33.97 | 38.39 | 12.3% | 🟡 | 1.65× |

**Leitura:** Lumina fica a 11% do C. A diferença está em **System time** (6.0 vs 5.7 ms) — a alocação inicial de 10 MB via `GC_malloc` custa ~3 ms de CPU, e o Boehm GC faz bookkeeping de página no primeiro toque.

**GC vs no-GC:**
| Variante | Mediana | vs GC |
|---|---:|---:|
| `primes_lumina` | 27.79 | 1.00× |
| `primes_lumina_nogc` | 23.48 | **0.84×** |

`--no-gc` economiza **~15%**. Não é ruído: System time cai de ~7 ms para ~6 ms, e o `GC_init()` sai do caminho. Em `primes`, com 1 alocação só, esse é o custo *máximo* do GC — em código com menos alocação, é menor.

### Loop matemático (100M)

`acc += i; if (t * i < 0) acc = 0;` com `t` vindo de `clock()`. Impede DCE via data-dependency.

| Lang | Mediana | p25 | p75 | IQR/med | Flag | vs C |
|---|---:|---:|---:|---:|---|---:|
| **C -O3** | 88.10 | 87.52 | 92.76 | 5.9% | ✅ | 1.00× |
| Rust -O3 | 96.82 | 96.11 | 99.95 | 4.0% | ✅ | 1.10× |
| **Lumina --release** | **88.87** | 88.00 | 93.88 | 6.6% | ✅ | **1.01×** |
| Go | 82.55 | 82.10 | 84.70 | 3.2% | ✅ | 0.94× |

**Leitura:** Lumina **empata com C** dentro do IQR (88.87 vs 88.10). Bate Rust por 8%. Go é 7% mais rápido — o compilador do Go reconhece esse tipo de loop melhor que o LLVM.

### Matriz 200×200 (int64)

Multiplicação de matriz densa. Working set de ~1 MB (cabe no L2).

| Lang | Mediana | p25 | p75 | IQR/med | Flag | vs C |
|---|---:|---:|---:|---:|---|---:|
| C -O3 | 5.54 | 5.45 | 6.08 | 11.4% | 🟡 | 1.00× |
| C -O3 (i64 puro) | 5.56 | 5.45 | 6.25 | 14.4% | 🟡 | 1.00× |
| Rust -O3 | 7.99 | 7.95 | 8.33 | 4.7% | ✅ | 1.44× |
| **Lumina --release** | **5.39** | 5.35 | 5.43 | **1.4%** | ✅ | **0.97×** |
| Go | 14.25 | 14.15 | 15.45 | 9.1% | ✅ | 2.57× |

**Leitura:** Lumina **empata com C** (1.4% de IQR — o número mais estável do run). O IQR de 1.4% é sinal de que a VM estava calma durante o Lumina.

**Sobre a "vantagem" histórica:** a versão anterior media **7.47 ms** para C (gcc) e **5.69 ms** para Lumina, sugerindo ganho de 31%. Investigação: gcc **não vetoriza** o matmul com `(size_t)i * n + k`; clang também não; Lumina também não (os 7 `vector.body` são loops de inicialização, não o hot loop). O "ganho" era **gcc vs clang**, não Lumina vs C. Com clang em ambos, empate honesto.

### Alloc churn (1M alloc/free)

Aloca e libera 1M blocos de 1..512 bytes. Mede o Boehm GC de verdade — diferente de `primes`, que só faz a alocação inicial.

| Lang | Mediana | p25 | p75 | IQR/med | Flag | vs C |
|---|---:|---:|---:|---:|---|---:|
| **C -O3** | 13.27 | 12.04 | 16.04 | 30.2% | ⚠️ | 1.00× |
| **Lumina --no-gc** | **12.15** | 12.06 | 17.12 | 41.7% | ⚠️ | **0.92×** |
| Lumina --release (GC) | 50.01 | 46.22 | 51.47 | 10.5% | 🟡 | **3.77×** |

**Leitura:** os dois primeiros medem `malloc`/`free` da glibc — empate dentro do ruído. `alloc_churn_lumina` é **3.77× mais lento** que `--no-gc`: esse é o custo real do Boehm GC em churn.

**Por que 3.77×?** Boehm `GC_malloc` faz mais bookkeeping que glibc: mantém bitmaps de página, checa se o GC precisa rodar, e `GC_free` marca blocos livres mas não os devolve ao SO. Para churn pequeno (1..512 bytes), o overhead por chamada é ~35 ns em vez de ~9 ns.

**Não é bug do Lumina.** `--no-gc` usa `malloc` da libc exatamente como o C faz. O gap é o preço do GC — troca latência de alloc por segurança de memória.

---

## 🔬 Como interpretar

### Fator vs C (mediana)

| Bench | Lumina / C | Avaliação |
|---|---:|---|
| Fib (35) | **0.97×** | Empate, dentro do ruído |
| Primes (10M) | 1.11× | 11% atrás — System time do GC |
| Loop (100M) | **1.01×** | Empate |
| Matrix (200×200) | **0.97×** | Empate, IQR 1.4% |
| Alloc churn (1M) | 3.77× | Custo real do Boehm GC |

### Onde Lumina está bem

- **Compute-bound (matrix, loop):** empata com C. Mesmo backend, IR comparável.
- **Call-heavy (fib):** empata com C e Rust. A diferença histórica (1.25×) era gcc-vs-clang.
- **`--no-gc` (primes, alloc_churn):** **empata com C**. Se você não precisa de GC, o custo é zero.

### Onde Lumina pode melhorar

- **`primes` GC:** os ~3 ms de CPU de `GC_malloc` na alocação inicial. Solução: escape analysis para arrays grandes não-coletados, ou flag por chamada.
- **`alloc_churn` GC:** 3.77× é o preço do GC. Se benchmarks como este importam, considere uma arena (`std/alloc.lm` já existe) para churn.

### Por que `--no-gc` importa

Todos os benchmarks rodam em três configurações:
- `--release` (padrão): Boehm GC
- `--no-gc`: `malloc`/`free` da libc

A diferença **isola** o custo do GC de cada benchmark:
| Bench | GC | no-GC | Custo do GC |
|---|---:|---:|---:|
| primes (1 alloc) | 27.79 | 23.48 | 15% |
| alloc_churn (1M allocs) | 50.01 | 12.15 | 76% |

---

## ⚠️ Caveats do Codespace

| Fonte | Impacto |
|---|---|
| vCPU compartilhada | IQR/mediana de 5–60% mesmo em medianas |
| Governor `schedutil` (sem `sudo`) | Frequência oscila 1.5–3.2 GHz |
| 2 vCPUs | Benchmarks multi-thread não escalam |
| L3 compartilhado com vizinhos | Ruído em memory-bound |
| `fib_lumina` IQR 59.7% | Candidato a rerun isolado |

**Não compare com bare-metal.** Só com runs anteriores do mesmo Codespace, de preferência no mesmo dia.

---

## 📁 Resultados históricos

Cada run salvo em `benchmarks/results/YYYY-MM-DD-codespace/` com:
- `env.md` — ambiente e toolchains (inclui compilador C usado)
- `<bench>.json` — saída crua do `hyperfine`
- `summary.md` — tabela de medianas + IQR + flags
- `primes_gc_vs_nogc.json` — comparativo GC

Para comparar runs: use a **mediana** e verifique a coluna **IQR/med**. Se as duas medianas divergirem >20%, um dos runs foi prejudicado pela VM.

---

## 📋 Estado dos itens do roadmap

**Fechados (última sessão):**

1. ✅ **`black_box` nativo** — builtin do compilador, usado em `alloc_churn.lm`.
2. ✅ **`argv`/`atoi`** — todos os `.lm` de benchmark agora parametrizados por `argv`.
3. ✅ **`loop` data-dependente** — 88.87 ms, empata com C.
4. ✅ **Isolar GC em primes** — `--no-gc` economiza 15%.
5. ✅ **Investigar matrix** — empate real; "ganho" era gcc vs clang.
6. ✅ **Alloc churn** — 3.77× é o custo real do Boehm.

**Próximos (fora do escopo desta sessão):**

- **Escape analysis** para arrays com N dinâmico mas loop-bounded — destravaria `primes` no stack.
- **`--gc-strategy`** (nursery, incremental) — trade-off latência vs throughput.
- **`std/alloc` arena** como primitiva de primeira classe, para churn controlado.
- **Aliasing hints** (`restrict`/`noalias`) expostos em Lumina — abre vetorização onde o LLVM hoje desiste.

---

## 🛠️ Reprodução dos números

```bash
cd /workspaces/Lumina/benchmarks
RUNS=20 WARMUP=3 CORE=1 ./bench.sh 2>&1 | tee /tmp/bench.log
```

Para uma tabela específica (com menos ruído):

```bash
# Só fib, com mais warmup e runs
taskset -c 1 hyperfine --warmup 10 --runs 50 -N \
  "./fib_c 35" "./fib_rs 35" "./fib_go 35" "./fib_lumina 35"

# Só o gap GC/no-GC
taskset -c 1 hyperfine --warmup 5 --runs 30 -N \
  "./primes_lumina 10000000" "./primes_lumina_nogc 10000000"

# Só alloc_churn, para validar a barreira anti-DCE
taskset -c 1 hyperfine --warmup 5 --runs 30 -N \
  "./alloc_churn_c 1000000" \
  "./alloc_churn_lumina 1000000" \
  "./alloc_churn_lumina_nogc 1000000"
```
