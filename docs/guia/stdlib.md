# 📦 Standard Library (`std/`)

Todos os módulos são escritos 100% em Lumina (bootstrapped), exceto onde indicado.

---

## Índice

- [Fundamentos](#fundamentos) — `prelude`, `math`, `str`, `string`, `result`
- [Coleções](#coleções) — `vector`, `map`, `set`, `deque`, `list`, `sort`, `iter`
- [Testes e Logging](#testes-e-logging) — `test`, `log`
- [I/O e SO](#io-e-so) — `io`, `fs`, `os`, `path`, `time`, `alloc`
- [Concorrência](#concorrência) — `channel`, `async`, `async_fs`, `epoll`, `net`, `http`
- [Integração](#integração) — `json`, `sqlite`, `raylib`

---

## Fundamentos

### `std/prelude` (auto-importado)

Define os tipos base disponíveis em todos os arquivos.

```lumina
enum Option:
    Some(int)
    None

enum Result:
    Ok(int)
    Err(int)
```

### `std/math`

```lumina
import "std/math"
```

| Função | Descrição |
|---|---|
| `potencia(base: float, exp: float) -> float` | `pow` da libc |
| `raiz_quadrada(val: float) -> float` | `sqrt` |
| `valor_absoluto(val: int) -> int` | `abs` |
| `chao(val: float) -> float` | `floor` |
| `teto(val: float) -> float` | `ceil` |
| `arredondar(val: float) -> float` | `round` |
| `abs_float(val: float) -> float` | `fabs` |
| `min(a: int, b: int) -> int` | mínimo |
| `max(a: int, b: int) -> int` | máximo |
| `clamp(v: int, lo: int, hi: int) -> int` | limita entre `lo` e `hi` |
| `gcd(a: int, b: int) -> int` | MDC |
| `lcm(a: int, b: int) -> int` | MMC |
| `powi(base: int, exp: int) -> int` | potência inteira (O(log n)) |
| `is_prime(n: int) -> int` | 1 se primo |
| `random_int(lo: int, hi: int) -> int` | aleatório no range |

### `std/str`

Funções de string (imutáveis):

| Função | Descrição |
|---|---|
| `to_upper(s: str) -> str` | MAIÚSCULAS (O(n) via StringBuilder) |
| `to_lower(s: str) -> str` | minúsculas |
| `trim(s: str) -> str` | remove espaços do início/fim |
| `ends_with(s: str, suffix: str) -> int` | 1 se termina com |
| `split(s: str, delimiter: str) -> ptr` | divide em array de `str` |
| `join(arr: ptr, delimiter: str) -> str` | junta array de `str` |
| `substr(s: str, start: int, length: int) -> str` | substring |
| `find(texto: str, alvo: str) -> int` | índice ou -1 |

### `std/string` (StringBuilder)

Para construção eficiente byte-a-byte:

```lumina
import "std/string"

mut sb = new_string_builder()
sb.push_str("hello")
sb.push_char(32)         # espaço
sb.push_str("world")
print(sb.finish())       # "hello world"
```

| Método | Descrição |
|---|---|
| `new_string_builder() -> StringBuilder` | cria vazio |
| `sb.reserve(min_cap: int)` | garante capacidade |
| `sb.push_char(c: int)` | adiciona byte |
| `sb.push_str(s: str)` | adiciona string |
| `sb.push_int(v: int)` | adiciona int (decimal) |
| `sb.push_float(v: float)` | adiciona float (6 casas) |
| `sb.finish() -> str` | finaliza (adiciona NUL) |
| `sb.clear()` | zera (mantém capacidade) |
| `sb.size() -> int` | bytes usados |

Diferente de `std/str` (funcional), `std/string` é **imperativo** e O(1) amortizado por byte.

### `std/result`

Helpers sobre `Result` (int-only por enquanto):

| Função | Descrição |
|---|---|
| `unwrap(r: Result) -> int` | payload se Ok; 0 se Err |
| `unwrap_or(r: Result, fallback: int) -> int` | payload ou default |
| `is_ok(r: Result) -> int` | 1 se Ok |
| `is_err(r: Result) -> int` | 1 se Err |
| `is_ok_and(r: Result, pred: fn) -> int` | 1 se Ok e pred(payload) |
| `expect(r: Result, msg: str) -> int` | payload ou imprime msg |
| `map(r: Result, f: fn) -> Result` | aplica f se Ok |
| `and_then(r: Result, f: fn) -> Result` | aplica f e achata |

```lumina
import "std/result"

let r = divide(10, 2)
print(is_ok(r))               # 1
print(unwrap(r))              # 5

let doubled = map(r, fn(x: int) -> int: x * 2)
print(unwrap(doubled))        # 10
```

---

## Coleções

Todas crescem automaticamente (rehash / resize).

### `std/vector`

```lumina
import "std/vector"

mut v = new_vector()
v.push(10)
v.push(20)
print(v.get(0))         # 10
print(v.pop())          # 20
print(v.sum())          # 10
```

| Método | Descrição |
|---|---|
| `new_vector() -> Vector` | cria vazio |
| `v.push(value: int)` | adiciona no fim |
| `v.pop() -> int` | remove último |
| `v.get(i: int) -> int` | acessa |
| `v.set(i: int, value: int)` | substitui |
| `v.len: int` | tamanho |
| `v.clear()` | esvazia (mantém capacidade) |
| `v.is_empty() -> int` | 1 se vazio |
| `v.sum() -> int` | soma |

### `std/map` (hash map `int → int`)

```lumina
import "std/map"

mut m = new_map()
m.insert(42, 100)
print(m.get(42))            # 100
print(m.contains(42))       # 1
print(m.remove(42))         # 1
```

| Método | Descrição |
|---|---|
| `new_map() -> Map` | cria vazio |
| `m.insert(key: int, value: int)` | insere/atualiza |
| `m.get(key: int) -> int` | -1 se não achar |
| `m.contains(key: int) -> int` | 1 se existe |
| `m.remove(key: int) -> int` | 1 se removeu |

### `std/set` (hash set de int)

```lumina
import "std/set"

mut s = new_set()
s.add(42)
print(s.contains(42))       # 1
print(s.remove(42))         # 1
```

### `std/deque`

Fila de dupla extremidade com buffer circular.

```lumina
import "std/deque"

mut d = new_deque()
d.push_back(1)
d.push_front(0)
print(d.pop_front())        # 0
print(d.pop_back())         # 1
```

### `std/list`

Lista ligada (mais lenta que Vector; use para aprender/benchmark).

### `std/sort`

```lumina
import "std/sort"

mut arr = alloc(5)
arr[0] = 5
arr[1] = 2
arr[2] = 8
arr[3] = 1
arr[4] = 9

sort(arr, 5)                    # crescente
sort_by(arr, 5, my_comparator)  # custom
print(is_sorted(arr, 5))        # 1
```

| Função | Descrição |
|---|---|
| `sort(arr: ptr, n: int)` | insertion (n ≤ 16) + quicksort |
| `sort_by(arr: ptr, n: int, cmp: fn(int, int) -> int)` | comparator |
| `is_sorted(arr: ptr, n: int) -> int` | 1 se ordenado |

Comparator pode ser closure com captura:

```lumina
let mult = 10
sort_by(arr, 4, fn(a: int, b: int) -> int: (b - a) * mult)
```

### `std/iter` (adaptadores funcionais)

```lumina
import "std/iter"

let nums = [1, 2, 3, 4, 5]
print(sum(nums, 5))                     # 15
print(map(nums, 5, fn(x: int) -> int: x * 2))
```

| Função | Descrição |
|---|---|
| `count_if(arr, n, pred) -> int` | conta elementos que satisfazem |
| `map(arr, n, f) -> ptr` | novo array com f aplicada |
| `filter(arr, n, pred) -> ptr` | elementos que satisfazem |
| `sum_by(arr, n, f) -> int` | soma de f(elem) |
| `sum(arr, n) -> int` | soma |
| `product(arr, n) -> int` | produto |
| `min(arr, n) -> int` / `max(arr, n) -> int` | min/max |
| `all(arr, n, pred) -> int` | 1 se todos |
| `any(arr, n, pred) -> int` | 1 se algum |
| `find_index(arr, n, pred) -> int` | índice ou -1 |
| `copy(arr, n) -> ptr` | cópia |
| `fill(arr, n, value)` | preenche |
| `for_each(arr, n, f)` | aplica in-place |
| `reverse(arr, n)` | inverte in-place |

---

## Testes e Logging

### `std/test`

```lumina
import "std/test"

test "1+1 = 2":
    return check_eq(1 + 1, 2, "soma")

test "string igual":
    return check_str_eq("a", "a", "str")
```

| Função | Descrição |
|---|---|
| `check_eq(actual, expected, msg) -> int` | 0 se igual |
| `check_ne(a, b, msg) -> int` | 0 se diferente |
| `check_true(cond: bool, msg) -> int` | 0 se true |
| `check_false(cond: bool, msg) -> int` | 0 se false |
| `check_str_eq(actual, expected, msg) -> int` | 0 se igual |

Rode com `lumina test arquivo.lm`.

### `std/log`

```lumina
import "std/log"

set_level(LOG_LEVEL_INFO)
log_debug("não aparece")     # abaixo do nível
log_info("iniciando")
log_warn("cuidado")
log_error("falhou")
```

| Função | Descrição |
|---|---|
| `set_level(level: int)` | 0=DEBUG, 1=INFO, 2=WARN, 3=ERROR |
| `get_level() -> int` | nível atual |
| `log_debug/…info/…warn/…error(msg: str)` | emite se `>= nível` |

---

## I/O e SO

### `std/io`

Streams e stdin:

```lumina
import "std/io"

let nome = read_line()
write_line("Olá, " + nome)
eprintln("(isso vai pro stderr)")
```

| Função | Descrição |
|---|---|
| `read_line() -> str` | linha sem `\n`; `""` em EOF |
| `read_int() -> int` | linha → int (via atoi) |
| `read_char() -> int` | 1 char de stdin |
| `write(s: str)` | stdout sem newline |
| `write_line(s: str)` | stdout + `\n` |
| `eprintln(s: str)` | stderr + `\n` |

Builtins usados internamente: `stdin()`, `stdout()`, `stderr()`, `fgets`, `fputs`, `fflush`, `getchar`.

### `std/fs`

```lumina
import "std/fs"
deletar_arquivo("caminho.txt")
```

### `std/os`

```lumina
import "std/os"

let home = get_env("HOME")
let d = cwd()
quit(0)                     # nunca retorna
sleep(100)                  # 100 ms
shell("ls -la")
```

| Função | Descrição |
|---|---|
| `get_env(name: str) -> str` | env var ou "" |
| `has_env(name: str) -> int` | 1 se existe |
| `cwd() -> str` | diretório atual |
| `quit(code: int)` | encerra |
| `shell(cmd: str) -> int` | roda via sh |
| `sleep(ms: int)` | dorme |

### `std/path`

```lumina
import "std/path"

print(join("src", "main.lm"))       # src/main.lm
print(basename("/usr/bin/ls"))      # ls
print(dirname("/usr/bin/ls"))       # /usr/bin
print(extension("a.txt"))           # .txt
print(stem("a.txt"))                # a
print(is_absolute("/usr"))          # 1
print(exists("."))                  # 1
print(is_dir("."))                  # 1
```

### `std/time`

```lumina
import "std/time"
let t = agora()             # clock() (CPU time)
```

### `std/alloc`

Arena allocator para bare-metal / alta performance:

```lumina
import "std/alloc"

mut a = init(1024)
let p = alloc(a, 16)        # O(1)
reset(a)
destroy(a)
```

---

## Concorrência

### `std/channel` (CSP estilo Go)

Canais com buffer, baseados em `pthread_mutex` + `pthread_cond`:

```lumina
import "std/channel"

let c = new(4)
send(c, 42)
let v = recv(c)
```

### `std/epoll` (Linux)

I/O assíncrono via `epoll` do kernel:

```lumina
import "std/epoll"

let fd = criar()
adicionar(fd, socket_fd)
let events = esperar(fd, 16)
```

### `std/net` / `std/http`

Servidores TCP/HTTP:

```lumina
import "std/http"

let fd = iniciar(8080)
# loop de accept + responder
```

### `std/async` / `std/async_fs`

Corrotinas (via `ucontext` — experimental) e I/O de arquivo não-bloqueante.

---

## Integração

### `std/json`

Parser simples:

```lumina
import "std/json"

let s = get_str("{\"name\":\"Lumina\"}", "name")   # "Lumina"
let v = get_int("{\"version\":10}", "version")     # 10
```

### `std/sqlite`

FFI para SQLite:

```lumina
import "std/sqlite"

let db = abrir("banco.db")
executar(db, "CREATE TABLE ...")
fechar(db)
```

### `std/raylib`

Bindings para a engine Raylib (jogos 2D/3D):

```lumina
import "std/raylib"

InitWindow(800, 600, "Meu Jogo")
while WindowShouldClose() == 0:
    BeginDrawing()
    ClearBackground(BLACK)
    DrawText("Olá", 10, 10, 20, RAYWHITE)
    EndDrawing()
CloseWindow()
```

Requer `[link] libs = ["raylib"]` no `lumina.toml`.