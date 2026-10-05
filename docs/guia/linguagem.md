# 📖 Referência da Linguagem Lumina

Referência completa da sintaxe e semântica. Para tutoriais, veja [Guia Rápido](guia-rapido.md).

---

## Índice

- [Tipos e Inferência](#tipos-e-inferência)
- [Arrays](#arrays)
- [Variáveis](#variáveis)
- [Operadores](#operadores)
- [Controle de Fluxo](#controle-de-fluxo)
- [Funções](#funções)
- [Tipos de Função](#tipos-de-função)
- [Closures](#closures)
- [Structs](#structs)
- [Enums e Pattern Matching](#tipos-algébricos-adts)
- [Generics](#generics)
- [Genéricos Aninhados](#genéricos-aninhados)
- [Impls e Traits](#impls-e-traits)
- [Type Aliases](#type-aliases)
- [Tuplas](#tuplas)
- [`nil` vs `none`](#nil-vs-none)
- [Macros](#macros)
- [`@derive`](#derive)
- [`@safe`](#safe)
- [LLVM Attrs](#llvm-attrs)
- [`defer`](#defer)
- [Módulos e Imports](#módulos-e-imports)

---

## Tipos e Inferência

Primitivos:

| Tipo | LLVM | Descrição |
|---|---|---|
| `int` | `i64` | Inteiro com sinal 64-bit |
| `float` | `f64` | Ponto flutuante 64-bit |
| `bool` | `i1` | Booleano |
| `str` | `i8*` | Ponteiro para string (null-terminated) |
| `ptr` | `i64*` | Ponteiro genérico (`alloc(N)` retorna isso) |
| `void` | `void` | Ausência de retorno |
| `fn` / `fn(T) -> R` | `{i8*, i8*}` | Fat pointer (fn ptr + env) |

Inferência:

```lumina
let x = 10               # int
let y = 3.14             # float
let s = "hello"          # str
let b = true             # bool
let nums = [1, 2, 3]     # ptr (array de int)
let t = (1, "a")         # tuple → ptr (LiteralStructType)
let r = Ok(42)           # Result<int, int> (inferido)
```

Promoção implícita:

```lumina
let x: float = 10        # int → float OK
let y: int = 3.14        # ERRO (truncaria)
```

---

## Arrays

Lumina tem duas formas de criar arrays:

### Array literal

```lumina
let v = [10, 20, 30]            # [i64;3]  — int
let precos = [1.5, 2.5, 3.5]    # [f64;3]  — float
let nomes = ["Ana", "Bob"]      # [i8*;2]  — str
```

O tipo do elemento é **inferido pelo primeiro elemento**. Não é
possível misturar tipos no mesmo array:

```lumina
let bad = [1, 2.5, 3]           # ERRO: 2.5 não cabe em i64
```

### Alocação dinâmica

```lumina
mut v = alloc(10)         # 10 × i64 (80 bytes)
mut buf = alloc_bytes(64) # 64 × i8  (64 bytes)
```

Ambos retornam um ponteiro para o primeiro elemento (`i64*` e `i8*`
respectivamente).

### Indexação

```lumina
print(v[0])       # int
print(precos[1])  # float
print(nomes[0])   # str

# Atribuição (precisa de `mut`)
mut w = [1, 2, 3]
w[1] = 42
```

### Iteração

```lumina
for x in v:
    print(x)

for i, x in v:    # índice + valor
    print(i, x)
```

`for i, x in v` declara `i` como `int` e `x` com o tipo do elemento.

### Slicing

```lumina
let s = v[1..3]     # elementos [1, 3)
let t = v[1..]      # do índice 1 até o fim
let u = v[..2]      # do início até índice 2
let w = v[..]       # cópia completa
```

O resultado é uma **cópia** em um novo buffer. O tipo do elemento é
preservado: slice de `[f64;N]` retorna `f64*`, slice de `[str;N]`
retorna `i8**`.

### Arrays em funções

Arrays literais preservam o tipo do elemento quando usados
diretamente:

```lumina
fn soma_float(v: float) -> float:
    return v[0] + v[1] + v[2]

fn main() -> int:
    let precos = [1.5, 2.5, 3.5]
    let total = soma_float(precos)
    print(total)
    return 0
```

**Limitação conhecida:** arrays passados como `ptr` (o tipo genérico)
para funções perdem a informação do tipo do elemento. Uma função
`fn soma(arr: ptr)` trata `arr[i]` como `int`, mesmo se o chamador
passou `[f64;N]`. Use tipos específicos (`fn soma_f64(v: f64)`) ou
converta explicitamente.

### Limitações conhecidas

* `alloc(N)` sempre produz `i64*`. Para arrays de outros tipos,
  use array literal ou `alloc_bytes` (que produz `i8*`).
* Não há verificação de bounds em runtime. `v[100]` num array de 3
  elementos é comportamento indefinido (leitura fora da memória).
* Não há `push`, `pop` ou resize. Para isso, use `std/vector`.

---

## Variáveis

```lumina
let x = 10               # imutável
mut y = 20               # mutável
z := 30                  # açúcar para `mut z = 30`
let p: Ponto             # declarar sem inicializar (zera campos)
```

Regras:

- `let` = imutável; reatribuir é erro de compilação.
- `mut` = mutável.
- `:=` = `mut` curto.
- Escopo é por bloco (indentação).
- Shadowing é permitido (mas `lumina lint` emite W002).

```lumina
fn main() -> int:
    let x = 10
    if true:
        let x = 20      # sombreia a externa (W002 do lint)
    return x            # 10
```

---

## Operadores

### Aritméticos

```lumina
+ - * / %
```

### Comparação

```lumina
== != < > <= >=
```

### Lógicos (com short-circuit)

```lumina
and or not
```

### Bitwise

```lumina
& | ^ ~ << >>
```

### Atribuição composta

```lumina
+= -= *= /= &= |= ^=
```

### Especiais

| Operador | Nome | Uso |
|---|---|---|
| `\|>` | Pipe | `5 \|> dobrar` = `dobrar(5)` |
| `?.` | Safe navigation | `u?.id` = 0 se `u == nil` |
| `?` | Propagação | `expr?` em função que retorna `Result` |
| `as` | Cast | `10 as float` |

### Precedência (baixo → alto)

```
logical (and/or)
bitwise_or
bitwise_xor
bitwise_and
comparison
shift
range (..)
additive
term
factor (unário, chamada, index)
```

---

## Controle de Fluxo

### `if` / `elif` / `else`

```lumina
if x > 10:
    print("grande")
elif x > 5:
    print("médio")
else:
    print("pequeno")
```

### `while`

```lumina
while x < 100:
    x = x + 1
```

### `for` (range)

```lumina
for i in 0..10:
    print(i)
```

### `for` (iterável)

```lumina
for n in [1, 2, 3]:       # array literal
    print(n)

for c in "abc":           # string
    print(c)

for n in arr:             # array via variável
    print(n)

for i, n in arr:          # índice + valor
    print(i, n)
```

### `break` / `continue`

```lumina
for i in 0..100:
    if i == 5:
        break
    if i % 2 == 0:
        continue
    print(i)
```

### `switch` (alias de `match` sobre `int`)

```lumina
switch dia:
    case 1: print("Domingo")
    case 2: print("Segunda")
    default: print("Outro")
```

### `assert`

```lumina
assert(1 == 1)          # OK
assert(1 == 2)          # aborta o processo
```

---

## Funções

```lumina
fn soma(a: int, b: int) -> int:
    return a + b

fn nada() -> void:
    print("oi")

fn com_default(a: int, b: int = 10) -> int:
    return a + b
```

### Argumentos nomeados

```lumina
soma(b: 20, a: 10)      # ordem livre
```

### Export (WASM)

```lumina
export fn fib(n: int) -> int:
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
```

### `extern fn` (FFI)

```lumina
extern fn puts(s: str) -> int
extern fn sqlite3_open(filename: str, db: str) -> int

fn main() -> int:
    puts("hello do libc")
    return 0
```

---

## Tipos de Função

```lumina
type Callback = fn(int) -> int

fn apply(f: Callback, x: int) -> int:
    return f(x)

fn apply2(f: fn(int, int) -> int, a: int, b: int) -> int:
    return f(a, b)
```

Regras:

- `fn` puro (sem assinatura) aceita **qualquer** função.
- `fn(T) -> R` exige arity e tipos em compile-time.
- Mistura tipado/untyped é permitida nos dois sentidos.
- **Campos de struct** podem ter tipo `fn`:

```lumina
struct Handler:
    cb: fn(int) -> int

fn main() -> int:
    mut h: Handler
    h.cb = fn(x: int) -> int: x * 2
    print(h.cb(21))     # 42
    return 0
```

---

## Closures

Sintaxe inline:

```lumina
let dobro = fn(x: int) -> int: x * 2
```

Sintaxe bloco:

```lumina
let add = fn(a: int, b: int) -> int:
    let s = a + b
    return s
```

Com captura (variável livre do escopo externo):

```lumina
fn main() -> int:
    let offset = 10
    let add = fn(x: int) -> int: x + offset
    print(add(5))       # 15
    return 0
```

**Captura por valor** — mutação posterior da variável externa não é vista:

```lumina
mut x = 10
let get = fn() -> int: x
x = 99
print(get())            # 10, não 99
```

Closures como callback (HOFs):

```lumina
import "std/sort"

let mult = 10
sort_by(arr, 4, fn(a: int, b: int) -> int: (b - a) * mult)
```

**Implementação:** todo valor `fn` é um **fat pointer** `{fn_ptr, env_ptr}`. O `env_ptr` carrega as capturas. Funções nomeadas usadas como valor são wrapped em runtime com `env_ptr = NULL`. `&fn_name` devolve o fn ptr **cru** (FFI-compatível).

---

## Structs

```lumina
struct Ponto:
    x: int
    y: int

struct Caixa:
    valor: int
    ponto: Ponto
```

Literal:

```lumina
let p = Ponto { x: 1, y: 2 }
let c = Caixa { valor: 10, ponto: p }
```

Acesso:

```lumina
print(p.x)              # 1
print(c.ponto.x)        # 1 (member chain)
```

Mutação:

```lumina
mut p: Ponto
p.x = 10
p.y = 20
```

Zerar sem inicializador:

```lumina
mut p: Ponto            # todos os campos = 0
```

Type check automático:

```lumina
let p = Ponto { x: "texto", y: 2 }   # ERRO em compile-time
```

---

## Tipos Algébricos (ADTs)

```lumina
enum Result:
    Ok(int)
    Err(int)

enum Par:
    Dois(int, int)
    Zero

enum Color:
    Red
    Green
    Blue
```

### Construção

```lumina
let r = Ok(42)
let p = Dois(10, 20)
let c = Red              # variante bare (sem payload)
```

Variante com payload usada bare é erro:

```lumina
let x = Ok                # ERRO: Ok espera payload
```

### Match

```lumina
match r:
    case Ok(v):  print("ok:", v)
    case Err(e): print("err:", e)
```

### Multi-payload com binding

```lumina
match p:
    case Dois(a, b): print(a, b)
    case Zero:       print(0, 0)
```

Payloads preservam tipo: `case Has(s): s + "!"` funciona quando o
payload é `str`, e `case Val(v): v * 2.0` quando é `float`.

### Guard

```lumina
match shape:
    case Circle(r) if r > 10: return "grande"
    case Circle(r):           return "pequeno"
    case Square(s):           return "quadrado"
```

### Multi-pattern e wildcard

```lumina
match n:
    case 1 | 2 | 3: return "pequeno"
    case 4 | 5:     return "médio"
    case _:         return "grande"
```

### Match em string

```lumina
match cmd:
    case "run":  return 1
    case "stop": return 0
    default:     return -1
```

### Match expressão

```lumina
let r = match x:
    case 1: 10
    case _: 20
```

---

## Generics

Função genérica:

```lumina
fn identidade<T>(x: T) -> T:
    return x

print(identidade(10))       # int
print(identidade(3.14))     # float
```

Struct genérica:

```lumina
struct Box<T>:
    data: T
```

Enum genérico:

```lumina
enum Res<T, E>:
    Ok(T)
    Err(E)

let r = Ok(42)              # Res<int, int> inferido
let s = Ok("hi")            # Res<str, int> inferido
```

**Monomorphization:** cada instanciação gera uma cópia especializada (`identidade__int`, `identidade__float`).

---

## Genéricos Aninhados

`Box<T>` como parâmetro de função:

```lumina
struct Box<T>:
    data: T

fn put<T>(b: Box<T>, val: T):
    b.data = val

fn get<T>(b: Box<T>) -> T:
    return b.data

fn main() -> int:
    mut bi: Box<int>
    mut bs: Box<str>
    put(bi, 42)
    put(bs, "hello")
    print(get(bi))    # 42
    print(get(bs))    # hello
    return 0
```

Suportado via `unify_type` (semantic) + `substitute_generic` (codegen).

---

## Impls e Traits

### `impl` simples

```lumina
struct Counter:
    n: int

impl Counter:
    fn inc():
        self.n = self.n + 1
    fn get() -> int:
        return self.n
```

### `impl` de trait

```lumina
trait Greeter:
    fn greet() -> int

impl Greeter for English:
    fn greet() -> int:
        return 0
```

### Trait com método default

```lumina
trait Greeter:
    fn name() -> str
    fn greet():
        print("Hi,", name())

struct English:
    dummy: int

impl Greeter for English:
    fn name() -> str:
        return "Lumina"
```

### `impl Box<T>:` (métodos em struct genérica)

O `<T>` é descartado para registro — vira `Box_get`:

```lumina
struct Box<T>:
    data: T

impl Box<T>:
    fn get() -> int:
        return self.data
```

### `impl Trait for Box<int>:` (especialização)

Preserva o tipo completo — vira `Box_int__metodo`:

```lumina
struct Box<T>:
    data: T

trait Kind:
    fn kind() -> int

impl Kind for Box<int>:
    fn kind() -> int:
        return 1

impl Kind for Box<str>:
    fn kind() -> int:
        return 2
```

As duas especializações coexistem. O lookup em chamadas tenta o nome completo primeiro e cai para o base.

### Operator overloading

```lumina
struct Vec2:
    x: int
    y: int

impl Vec2:
    fn __add__(a: Vec2, b: Vec2) -> Vec2:
        mut r: Vec2
        r.x = a.x + b.x
        r.y = a.y + b.y
        return r
```

Operadores suportados: `__add__`, `__sub__`, `__mul__`, `__div__`, `__eq__`, `__ne__`, `__lt__`, `__gt__`, `__le__`, `__ge__`.

---

## Type Aliases

Simples:

```lumina
type MyInt = int
type Callback = fn(int) -> int
type P = Ponto
```

Genéricos:

```lumina
struct Pair<A, B>:
    a: A
    b: B

type IPair<B> = Pair<int, B>
```

Uso em qualquer posição:

```lumina
fn soma(p: P) -> int:
    return p.x + p.y

fn apply(f: Callback, x: int) -> int:
    return f(x)

fn get(p: IPair<str>) -> int:
    return p.a
```

Aliases encadeiam:

```lumina
type A = int
type B = A
type C = B        # C == int
```

A expansão acontece na **passada 0 do semantic** — o resto do pipeline nunca vê o alias.

---

## Tuplas

Literais:

```lumina
let t = (1, 2, 3)
let u = (42, "hello")       # tipos heterogêneos
```

Destructuring:

```lumina
let (a, b, c) = (1, 2, 3)

# Sobre struct
let (x, y) = ponto

# Sobre array
let (p, q) = arr
```

Parênteses **não** são tupla:

```lumina
let x = (1 + 2) * 3        # 9, não tupla
```

---

## `nil` vs `none`

| | `nil` | `none` |
|---|---|---|
| Representa | null pointer C-style | `Option::None` |
| Tipo | `ptr` / `str` / `fn` / struct | `Option<T>` |
| Uso | `if u == nil`, `u?.campo` | `match x: case None:` |

`nil`:

```lumina
struct U:
    id: int

fn main() -> int:
    let u: U = nil
    if u == nil:
        print("nil")
    let v = u?.id           # 0 (safe nav)
    return 0
```

`none`:

```lumina
fn main() -> int:
    let x: Option = none
    match x:
        case Some(v): print(v)
        case None:    print("none")
    return 0
```

---

## Macros

Lumina tem **duas formas** de macro:

### `@macro` de expressão (`nome(args)`)

Corpo deve ser **um único** `return <expr>`:

```lumina
@macro
fn dobro(x: int) -> int:
    return x * 2

fn main() -> int:
    let a = 5
    print(dobro(a + 1))     # (a + 1) * 2 = 12
    return 0
```

Expansão inline no call site.

### `@macro` de statement (`nome!(args)`)

Corpo pode ter múltiplos statements:

```lumina
@macro
fn soma_em(p: ptr, idx: int, val: int):
    p[idx] = p[idx] + val

fn main() -> int:
    mut arr = alloc(3)
    arr[0] = 0
    arr[1] = 0
    arr[2] = 0
    for i in 0..3:
        soma_em!(arr, i, i + 1)
    print(arr[0], arr[1], arr[2])   # 1 2 3
    return 0
```

`return` dentro da macro-stmt retorna da função **chamadora**:

```lumina
@macro
fn early_exit(cond: int):
    if cond == 0:
        return 42

fn f(x: int) -> int:
    early_exit!(x)
    return 100

f(0)    # 42
f(1)    # 100
```

---

## `@derive`

Sintetiza métodos de trait no `struct`:

```lumina
@derive(Eq, PartialEq, Debug, Display, Clone, Default)
struct Ponto:
    x: int
    y: int
```

| Derive | Gera |
|---|---|
| `Eq` / `PartialEq` | `__eq__` (e `__ne__` para PartialEq) |
| `Debug` / `Display` | `__debug__` (retorna `str`) |
| `Clone` | `clone()` |
| `Default` | função livre `new_Ponto()` |

Uso:

```lumina
let p1 = Ponto { x: 1, y: 2 }
let p2 = p1.clone()
print(p1 == p2)             # true
print(p1.__debug__())       # Ponto { x: 1, y: 2 }
```

`@derive` em `enum` ainda não é suportado (erro em compile-time).

---

## `@safe`

Null check automático em `MemberExpr` e `IndexExpr`:

```lumina
struct U:
    id: int

@safe
fn get_id(u: U) -> int:
    return u.id             # 0 se u == nil

fn main() -> int:
    let u: U = nil
    print(get_id(u))        # 0 (sem SIGSEGV)
    return 0
```

Sem `@safe`, `u.id` com `u == nil` causa SIGSEGV (rápido mas perigoso).

---

## LLVM Attrs

| Attr | Efeito |
|---|---|
| `@inline` | `alwaysinline` |
| `@noinline` | `noinline` |
| `@cold` | `cold` (ramo improvável) |
| `@hot` | `inlinehint` (mapeado — LLVM `hot` é string attribute) |

```lumina
@inline
fn dobro(x: int) -> int:
    return x * 2
```

`@inline` + `@noinline` juntos = erro de compilação.

---

## `defer`

Escopo de **bloco** (Go/Zig-style):

```lumina
fn main() -> int:
    defer print("fim da função")

    if true:
        defer print("fim do if")
        print("dentro do if")
        # Saída: dentro do if / fim do if

    for i in 0..2:
        defer print("fim da iteração")
        print(i)
        # Saída: 0 / fim da iteração / 1 / fim da iteração

    print("depois do loop")
    return 0
# Saída: depois do loop / fim da função
```

`defer` dentro de `if false` **não** roda.

---

## Módulos e Imports

```lumina
import "std/math"
import "std/io"
import "meu_modulo"
```

Resolução de caminhos:

- `std/X` → `std/X.lm`
- `./foo` → `foo.lm` (relativo)
- `meu_modulo` → `lumina_modules/meu_modulo.lm` (dependência)

`std/prelude.lm` é auto-importado (`Option`, `Result`).

### `[link]` no `lumina.toml`

```toml
[link]
libs = ["m", "raylib"]
extra_objects = ["helper.cpp"]
extra_flags = ["-DFOO=1", "-Iinclude"]
target = "wasm"
```

O `cmd_build` procura por `[link]` em:
1. Sidecar: `examples/engine.lm` → `examples/engine.toml`
2. Raiz: `./lumina.toml`