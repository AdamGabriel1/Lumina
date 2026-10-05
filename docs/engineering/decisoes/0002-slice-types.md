---
status: proposto
data: 2026-10-02
autores: [Adam Gabriel]
revisores: []
---

# ADR 0002 — Slice Types (`[T]`)

## Resumo

Introduz o tipo `[T]` ("slice") representando uma **view tipada e com
comprimento** sobre uma região contígua de memória. Resolve a
limitação conhecida de `for x: T in ptr` (loop vazio por falta de
comprimento) e prepara o terreno para APIs de stdlib mais ergonômicas
e para o self-hosting.

## Contexto

### O problema

Hoje, um array em Lumina é `ptr` (ponteiro para o primeiro elemento).
O compilador perde duas informações críticas ao passar por funções:

1. **Tipo do elemento** — `[1.5, 2.5]` vira `i64*` (mesmo ponteiro).
2. **Comprimento** — `fn f(arr: ptr, n: int)` recebe `n` separado.

Consequências:

```lumina
fn sum(arr: ptr, n: int) -> float:
    mut total = 0.0
    for x: float in arr:    # ← loop vazio, `n` ignorado
        total += x
    return total
```

A anotação `for x: float in arr` introduzida em v0.7.0 resolve o
problema de **tipo** mas não o de **comprimento**. O codegen só
itera quando `array_lengths[arr]` está populado (array literal ou
`alloc(N)` com N literal). Parâmetros caem no fallback de loop vazio.

### Inventário de limitações relacionadas

| Situação | Estado atual | Impacto |
|---|---|---|
| `fn f(arr: ptr, n: int)` + `for x in arr` | Loop vazio | **Alto** — APIs de stdlib |
| `v[1..3]` de `[f64;N]` | Copia para `f64*` (perde len) | Médio |
| `v[1..3]` de `str` | Copia string | OK (string tem len) |
| Retorno de sub-array | Não há forma | Alto |
| `std/sort::sort(arr, n)` | Dupla param | Ergonômico mas verboso |

### Requisitos

1. **Retrocompatibilidade** — código existente não pode quebrar.
2. **Ergonomia** — `fn sum(s: [float]) -> float` deve ser possível.
3. **Zero-copy** — slices são views, não cópias.
4. **Integração com `for`, `len`, indexação** — deve funcionar como
   array hoje funciona.
5. **Consistência com safe-default** — bounds check em `s[i]` quando
   em modo safe.
6. **Preparação para self-hosting** — o lexer/parser em `.lm` precisa
   passar tokens entre fases sem cópia.

## Alternativas consideradas

### Alternativa 1: `Slice<T>` explícito

```lumina
struct Slice<T>:
    data: ptr
    len: int

fn sum(s: Slice<float>) -> float:
    mut total = 0.0
    mut i = 0
    while i < s.len:
        total += s.data[i] as float
        i += 1
    return total
```

**Prós:** zero mudanças de lexer/parser.
**Contras:** verboso, precisa de cast manual, não integra com `for`.

### Alternativa 2: `[]T` (Go-style)

```lumina
fn sum(s: []float) -> float:
    ...
```

**Prós:** familiar para Go devs, conciso.
**Contras:** `[]` em posição de tipo pode conflitar com array literal
vazio `[]` em expressões. Ambiguidade no parser.

### Alternativa 3: `T[]` (C#/Java-style)

```lumina
fn sum(s: float[]) -> float:
    ...
```

**Prós:** familiar.
**Contras:** parser precisa lookahead para distinguir `T[]` de
`T[]` (indexação de `T`). Ambiguidade real.

### Alternativa 4: `&[T]` (Rust-style)

```lumina
fn sum(s: &[float]) -> float:
    ...
```

**Prós:** semanticamente explícito (referência).
**Contras:** `&` já é `AddressOfExpr`. Overload do token.

### Alternativa 5: `[T]` (Swift/Rust-type-style)

```lumina
fn sum(s: [float]) -> float:
    ...
```

**Prós:** conciso, sem ambiguidade (contexto de tipo vs. expressão).
**Contras:** `[T]` como tipo precisa entrar no parser de tipos.

### Alternativa 6: Não fazer nada

Manter `ptr` + `n` como protocolo manual.

**Prós:** zero risco.
**Contras:** limitação permanente, APIs ficam feias, self-hosting
sofre.

## Decisão

Adotar **Alternativa 5 (`[T]`)** com as seguintes regras:

### Sintaxe

1. **Tipo:** `[T]` em posição de tipo.

   ```lumina
   fn sum(s: [float]) -> float: ...
   fn process(items: [str]): ...
   struct Container:
       items: [int]
   ```

2. **Construção por slice expression:** `v[a..b]` retorna `[T]`.

   ```lumina
   let v = [1.5, 2.5, 3.5]
   let s = v[0..2]     # s : [float], view dos 2 primeiros
   let all = v[..]     # view completa
   ```

3. **Construção explícita:** `Slice { data: p, len: n }`.

   ```lumina
   fn make(p: ptr, n: int) -> [int]:
       return Slice { data: p, len: n }
   ```

4. **Builtin `as_slice`** para conversão de `ptr` + `n`:

   ```lumina
   let s = as_slice(p, n)   # p : ptr, n : int → [int]
   ```

### Consumo

1. **Iteração:** `for x in s:` funciona como em arrays.
   ```lumina
   for x in s:
       print(x)
   ```

2. **Indexação:** `s[i]` com bounds check em modo safe.
   ```lumina
   let primeiro = s[0]
   ```

3. **Comprimento:** `len(s)` retorna `s.len`.
   ```lumina
   print(len(s))
   ```

4. **Fields:** `s.data` e `s.len` acessíveis.
   ```lumina
   print(s.data)   # ptr
   print(s.len)    # int
   ```

5. **Sub-slicing:** `s[a..b]` retorna `[T]` (view dentro da view).
   ```lumina
   let sub = s[1..3]
   ```

### Representação LLVM

`[T]` é uma struct identificada `%Slice_T_` com dois campos:

```llvm
%Slice_i64_        = type { i64*,    i64 }
%Slice_f64_        = type { double*, i64 }
%Slice_i8p_        = type { i8**,    i64 }
%Slice_Slice_int__ = type { %Slice_int_*, i64 }   ; aninhado
```

Monomorphização: cada instanciação gera um tipo novo sob demanda,
como `Box<T>` já faz.

### ABI

Passada por **ponteiro** (`%Slice_T_*`), consistente com o resto
das structs Lumina.

### Compatibilidade com `ptr`

`ptr` continua sendo `i64*`. Slices **não** são automaticamente
atribuíveis a `ptr`:

```lumina
let s: [int] = ...
let p: ptr = s          # ERRO — use `s.data`
let p: ptr = s.data     # OK
```

Isso evita que um slice perca `.len` silenciosamente.

### Compatibilidade com array literal

Array literais continuam produzindo `ptr` (compat):

```lumina
let v = [1, 2, 3]       # v : ptr
let s: [int] = v        # ERRO hoje → mudança: OK, via coerção
```

Regra **nova** (breaking minor):
`let s: [int] = v` onde `v` é array literal **passa a funcionar** —
o codegen usa `array_lengths[v]` para construir o slice.

Se `v` não tem comprimento conhecido (parâmetro, retorno de função),
a atribuição falha com mensagem clara.

### Breaking changes

1. **`v[a..b]` muda de semântica.**

   | Antes (v0.7.x) | Depois (v0.8.0) |
   |---|---|
   | Copia para `T*` | View `[T]` |
   | `malloc` + loop | ZERO alocação |
   | `arr[1..3]` retorna `T*` | retorna `[T]` |

   **Migração:** use `copy(v[a..b])` (builtin novo) para o
   comportamento antigo.

   **Deprecation:** em v0.7.x, adicionar flag `--legacy-slice-copy`
   que restaura o comportamento antigo e emite warning. Remover em
   v0.9.0.

2. **`v[..]` de `str` continua retornando `str`.**

   Strings têm tratamento especial — `len` é calculado por `strlen`.
   Slice de string (bytes) é acessível via `s.bytes()`.

3. **`s[i]` em modo safe adiciona bounds check.**

   Consistente com safe-default. Custo: ~3 instruções por acesso.

## Implementação — fases

### Fase 1: Tipo + construções (v0.8.0-alpha)

**Arquivos:**
- `lumina/ast/types.py` — novo nó `SliceType(inner_type: str)`
- `lumina/parser/expressions.py::parse_type` — reconhece `[T]`
- `lumina/semantic/types.py` — `is_assignable` para slices
- `lumina/codegen/types.py` — `get_llvm_type("[T]")` retorna `%Slice_T_*`
- `lumina/codegen/setup.py` — registra builtin `Slice` (struct genérica)

**Entregável:** `fn f(s: [int]) -> int: return s.len` compila e roda.

### Fase 2: SliceExpr retorna `[T]` (v0.8.0-beta)

**Arquivos:**
- `lumina/semantic/expressions/literals.py::visit_SliceExpr` — retorna `[T]`
- `lumina/codegen/expressions/members.py::visit_SliceExpr` — constrói struct
- `lumina/codegen/expressions/aggregates.py` — `Slice { data, len }` literal

**Entregável:** `let s = v[1..3]; print(s[0])` funciona.

### Fase 3: Consumo (`for`, `len`, indexação) (v0.8.0-rc)

**Arquivos:**
- `lumina/codegen/statements/control.py::_visit_for_iterable` — detecta `[T]`
- `lumina/codegen/expressions/builtins.py::_call_builtin_impl` — `len` aceita slice
- `lumina/codegen/expressions/members.py::visit_IndexExpr` — indexa slice

**Entregável:** `for x in v[1..3]: print(x)` funciona.

### Fase 4: Builtins auxiliares (v0.8.0)

**Novos builtins:**
- `as_slice(p: ptr, n: int) -> [T]` — conversão
- `copy(s: [T]) -> ptr` — comportamento antigo de `v[a..b]`
- `sub_slice(s: [T], a: int, b: int) -> [T]` — sub-slicing explícito (opcional)

**Entregável:** APIs de migração disponíveis.

### Fase 5: Migração de `std/*` (v0.8.x)

**Assinaturas duais:**
- `sort(arr: ptr, n: int)` — mantido
- `sort_slice(s: [int])` — novo, delega

Ou **overload por assinatura** (se implementado em v0.8.x).

**Entregável:** stdlib mais ergonômica sem quebrar usuários.

### Fase 6: Deprecation (v0.9.0)

Remover `--legacy-slice-copy`. `v[a..b]` agora **sempre** retorna `[T]`.

## Consequências

### Positivas

- **Resolve a limitação `for x: T in ptr`** — o caso
  `test_limitation_ptr_without_length` vai virar teste de sucesso.
- **APIs de stdlib mais limpas** — `fn find(haystack: [str], needle: str) -> int`
  em vez de `(ptr, n)`.
- **Sub-slicing zero-copy** — `s[1..3]` de slice é O(1).
- **Preparação para self-hosting** — lexer/parser em `.lm` podem
  passar `[Token]` entre fases.
- **Bounds check opcional** — integrado com safe-default.

### Negativas

- **Breaking change em `v[a..b]`** — migração necessária.
- **Complexidade no semantic** — mais um tipo, mais `is_assignable`.
- **Monomorphização** — cada `[T]` distinto gera um `%Slice_T_`.
- **Bounds check em `s[i]`** — custo em modo safe.
- **Interação com `str`** — regra especial.
- **`alloc(N)` continua `ptr`** — assimetria com slices explícitos.

### Riscos

1. **Parser ambiguity** — `[T]` em posição de tipo vs. expressão.
   Mitigado por contexto (`parse_type` vs. `parse_expression`).

2. **ABI incompat com C** — `[T]` como struct por ponteiro não é
   `{T*, i64}` passado por valor. FFI para C esperaria `(T*, i64)`.
   Mitigação: `as_ptr(s)` e `as_slice(p, n)` para cruzar a fronteira.

3. **Migração de `std/*`** — quebra APIs internas.
   Mitigação: assinaturas duais.

## Métricas de sucesso

- `test_limitation_ptr_without_length` removido ou invertido.
- Novo teste `test_slice_basic.py` com ≥ 10 casos.
- `std/sort.lm` ganha wrapper `sort_slice`.
- Exemplos `iterator_test.lm`, `iter_test.lm` reescritos para slices.
- Benchmarks `primes.lm` e `matrix.lm` compilam sem mudanças (compat).

## Perguntas abertas

1. `[T]` deve ser **mutável** por default ou precisa `mut [T]`?
   Decisão pendente — provavelmente mutável, como `ptr` hoje.

2. `Slice<T>` (nome canônico) vs `[T]` (açúcar) — qual aparece em
   mensagens de erro?
   Decisão: `[T]` em todas as mensagens de usuário.

3. Coerção implícita `[T] → ptr` para compat com APIs legadas?
   Decisão: **não** — explícito `s.data`.

4. Como `for x in v[1..3]` interage com `array_lengths`?
   `array_lengths` só se aplica a variáveis com nome. `v[1..3]` é
   expressão — usa `.len` do slice construído.

5. Bounds check em `s[i]` com índice negativo — `i < 0`?
   Sim — safe mode retorna 0, unsafe é UB.

## Referências

- **Go spec** — slices como `{ptr, len, cap}` (cap removido aqui).
- **Rust `&[T]`** — `(ptr, len)` fat pointer, zero-copy.
- **Swift `ArraySlice`** — view com bounds independentes.
- **Zig `[]T`** — slice com `.ptr` e `.len`.
- **C++20 `std::span`** — view com `.data()` e `.size()`.

## Aprovação

| Revisor | Status | Data |
|---|---|---|
| (a preencher) | | |

---

## Apêndice A — Exemplos comparativos

### Antes (v0.7.x)

```lumina
fn sum(arr: ptr, n: int) -> float:
    mut total = 0.0
    mut i = 0
    while i < n:
        total += arr[i] as float
        i += 1
    return total

fn main() -> int:
    let v = [1.5, 2.5, 3.5]
    print(sum(v, 3))
    return 0
```

### Depois (v0.8.0)

```lumina
fn sum(s: [float]) -> float:
    mut total = 0.0
    for x in s:
        total += x
    return total

fn main() -> int:
    let v = [1.5, 2.5, 3.5]
    print(sum(v[..]))
    return 0
```

## Apêndice B — IR comparativo

### `fn sum(s: [float])` — v0.8.0

```llvm
%Slice_f64_ = type { double*, i64 }

define double @"sum"(%Slice_f64_* %".1") {
sum_entry:
  %"s" = alloca %Slice_f64_*
  store %Slice_f64_* %".1", %Slice_f64_** %"s"
  br label %"sum_body"
sum_body:
  ; .data e .len carregados
  %".2" = getelementptr %Slice_f64_, %Slice_f64_* %".1", i32 0, i32 0
  %"data" = load double*, double** %".2"
  %".3" = getelementptr %Slice_f64_, %Slice_f64_* %".1", i32 0, i32 1
  %"len" = load i64, i64* %".3"
  ; for loop
  ...
}
```

## Apêndice C — Glossário

- **Slice**: view sobre região contígua, com ponteiro + comprimento.
- **Fat pointer**: representação de dois words (ptr + metadata).
- **View**: referência sem posse (não libera).
- **Bounds check**: verificação `0 <= i < len` antes de acessar.

---

**Fim da ADR 0002.**
