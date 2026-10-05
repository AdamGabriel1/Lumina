---
status: proposto
data: 2026-09-25
autores: [Adam Gabriel]
revisores: []
---

# ADR 0004 — Hygiene automática em macros

## Resumo

Torna **automática** a renomeação de bindings introduzidos por
`quote:` dentro de macros `@macro`, eliminando a necessidade de
`gensym()` manual. Bindings locais da macro recebem nomes mangled
(`__<macro>_<name>_<N>`); símbolos livres (referências que apontam
para o escopo externo) permanecem intocados; `~x` (unquote)
preserva o nome do argumento como aparece no call site.

É a evolução natural da ADR 0003. A ADR 0003 entregou quasiquote
com hygiene **manual** e explicitou que a v1 seria manual, "v2
(futuro): automática por padrão". Esta ADR fixa o design dessa v2.

Alvo: **v1.1**.

## Contexto

### Estado atual (v1.0)

A ADR 0003 introduziu `quote:` / `~` / `~@` e `gensym()` como
primitiva de hygiene **manual**. O corpo de uma macro é
interpretado pelo `QuoteInterpreter` (`lumina/codegen/quote_eval.py`),
que constrói AST em compile-time.

Hygiene hoje:

```lumina
@macro
fn swap(a, b):
    let tmp = gensym("swap_tmp")
    quote:
        let ~tmp = ~a
        ~a = ~b
        ~b = ~tmp
```

O usuário é responsável por chamar `gensym` para **cada** binding
introduzido por `quote:`. Sem isso:

### O problema

**Caso 1: colisão silenciosa com o call site.**

```lumina
@macro
fn twice(x):
    quote:
        let tmp = ~x
        tmp + tmp

fn main() -> int:
    let tmp = 42
    let r = twice(tmp)     # qual `tmp` está sendo somado?
    print(tmp)             # 42 — mas por sorte
    return 0
```

Hoje, `_build_stmt` reconstrói o `VarDecl("tmp", ...)` com o nome
literal `"tmp"`. No call site, o codegen faz `builder.alloca(..., name="tmp")`
em um slot que **sombra** o `tmp` do usuário. A expansão produz:

```lumina
# pseudo-AST pós-expansão
let tmp = tmp       # ← RHS resolve para o `tmp` do usuário (42)
tmp + tmp           # ← 84
```

Funciona **por acidente**: o `alloca` é feito no mesmo escopo, e o
RHS é avaliado antes do `store`. Mas basta reordenar:

```lumina
@macro
fn broken(x):
    quote:
        let tmp = 1
        let tmp2 = ~x
        tmp + tmp2      # usa tmp=1, tmp2=x

fn main() -> int:
    let tmp = 100
    print(broken(tmp))  # quer 101, obtém ? (depende da ordem)
    return 0
```

E o pior caso: **múltiplas invocações** da mesma macro no mesmo
escopo:

```lumina
fn main() -> int:
    print(twice(1))
    print(twice(2))     # segundo `let tmp` colide com o primeiro
    return 0
```

O LLVM aceita (SSA renomeia), mas o semantic **não** distingue
escopos de macro: se o usuário tem `tmp` visível, a resolução é
ambígua.

**Caso 2: referências livres capturam errado.**

```lumina
@macro
fn log_and(x):
    quote:
        print("checking")
        ~x

fn main() -> int:
    let print = 42      # shadowing do builtin
    log_and(1 == 1)
    return 0
```

O `print` na macro deve resolver para o **builtin** (escopo de
definição da macro), não para a variável local `print` do usuário.
Hoje resolve para o `print` local — a macro quebra silenciosamente.

**Caso 3: atrito.**

Toda macro não-trivial precisa de 2-3 chamadas `gensym`:

```lumina
@macro
fn unless(cond, body):
    let tmp_cond = gensym("cond")
    let tmp_body = gensym("body")
    quote:
        let ~tmp_cond = ~cond
        if not ~tmp_cond:
            ~body
```

Isso é boilerplate puro. O usuário não *quer* gerenciar nomes
únicos; ele quer escrever a macro.

### Inventário de limitações relacionadas

| Situação | Estado atual | Impacto |
|---|---|---|
| `let tmp` em `quote:` + `tmp` no call site | Colisão silenciosa | **Alto** |
| `print` na macro + `print` shadowed no call site | Captura errada | **Alto** |
| Duas invocações da mesma macro no mesmo escopo | Colisão de slots | Médio |
| Macro que quer nome fixo (`route!` expõe `path`) | Sem escape hatch | Médio |
| Erro em código gerado mostra nome mangled | Se `gensym` foi usado | Baixo |

### Casos de uso almejados

1. **`swap(a, b)`** — sem `gensym` explícito, o `tmp` interno deve
   ser invisível ao usuário.

2. **`twice(x)`** — `let tmp = ~x; tmp + tmp` deve poder ser escrito
   sem pensar.

3. **`route!(method, path, handler)`** — quer **expor** `path` ao
   `handler`:

   ```lumina
   @macro
   fn route(method, path, handler):
       quote_raw:
           if ~method == "GET" and ~path == path:
               ~handler()
   ```

   Aqui, `path` (fixo) é **intencionalmente** visível no `handler`.
   Precisa de escape hatch.

4. **Macros aninhadas** — `double(x)` chamando `quad(x)` não deve
   ver o `tmp` da interna.

5. **`@derive` generalizado** — `@derive(Eq)` reimplementado em
   `std/derives.lm` (ver ADR 0003 §"Fase 5") vai gerar dezenas de
   `VarDecl` por struct. Sem hygiene automática, cada um precisaria
   de `gensym`.

### Requisitos

1. **Correção.** Bindings da macro não colidem com o call site.
2. **Retrocompatibilidade.** Código que usa `gensym` continua
   funcionando — o renaming é no-op quando o nome já é mangled.
3. **Erros com nome original.** Se um erro cita `__twice_tmp_1`, a
   mensagem deve mostrar `tmp`.
4. **Escape hatch.** Macros que **querem** introduzir nomes fixos
   (DSLs) precisam de opt-out.
5. **Zero overhead em runtime.** É puramente compile-time.
6. **Composabilidade.** Macros aninhadas têm hygiene independente.
7. **Sem reescrever o resolver de nomes.** O semantic atual resolve
   nomes por string; não queremos introduzir um sistema de escopos
   léxicos completo.
8. **Diagnósticos.** Erros continuam apontando para o call site.

## Alternativas consideradas

### Alternativa 1: Alpha-renaming durante expansão

Toda variável **declarada** dentro de `quote:` (i.e., que aparece
em `VarDecl`, `ForStmt.var_name`, `ForStmt.index_var`) é
renomeada para `__<macro>_<name>_<N>`. Referências a esse nome
dentro do mesmo `quote:` são reescritas para o mangled. Símbolos
livres (referências sem binding local) permanecem intocados.

```lumina
@macro
fn twice(x):
    quote:
        let tmp = ~x      # → VarDecl("__twice_tmp_1", ...)
        tmp + tmp         # → BinaryExpr('+', Var("__twice_tmp_1"), ...)

fn main() -> int:
    let tmp = 42
    twice(tmp)            # nenhum binding `tmp` introduzido
    return tmp            # 42 — sem ambiguidade
```

**Prós:**
- Implementável em ~150 linhas no `QuoteInterpreter`.
- Backwards-compatible: `gensym()` já produz nome mangled, então o
  renaming é no-op para código existente.
- Não requer info nova do parser.
- Não requer mudança no semantic (o mangled é só um identificador
  como outro qualquer).
- Preserva `~x` (unquote) sem renomear — é isso que permite
  macro capturar variáveis do call site.

**Contras:**
- Hygiene "rasa": não cobre macros que constroem código que
  depende de convenção do call site (e.g., `route!` espera `path`).
  Mitigação: `quote_raw:`.
- Símbolos livres (ex: `print`) permanecem resolvidos no call site.
  Isso é o comportamento atual e desejado em Lumina (não há
  módulos com escopo léxico completo ainda).

### Alternativa 2: Hygiene total (Racket-style)

Cada símbolo carrega um **escopo léxico** (marca de origem).
Quando um `VariableExpr` é resolvido, o escopo é consultado.

```lumina
# `print` na macro carrega o escopo `mymodule::log_and`
# `print` no call site carrega `main`
# Resolver: escolhe o escopo de definição da macro
```

**Prós:**
- Modelo correto e completo (Racket, Scheme `syntax-rules`).
- Cobre todos os casos, incluindo macros que querem expor nomes.

**Contras:**
- Requer reescrever todo o resolver de nomes do semantic
  (`lumina/semantic/analyzer.py::get_var_info` e todos os `visit_*`)
  para entender escopos.
- Introduz uma camada de indireção em **toda** lookup de variável.
- ~3-4 semanas de trabalho, com risco alto de regressão.
- O ganho marginal sobre a Alternativa 1 é pequeno para Lumina,
  que não tem sistema de módulos com escopo léxico (ainda).

### Alternativa 3: Manter manual (`gensym`)

Nada muda. Documenta-se mais e confia-se em disciplina do usuário.

**Prós:**
- Zero risco.
- Zero trabalho.

**Contras:**
- Bugs silenciosos continuam.
- Atrito alto em macros não-triviais.
- A ADR 0003 já prometeu "v2 automática". Manter manual é dívida.

### Alternativa 4: Macro como procedimento (Rust-style)

Mudar `@macro` para um sistema de macros procedurais que roda
código Rust (ou Lumina) no parser.

```lumina
@proc_macro
fn derive_eq(input: TokenStream) -> TokenStream:
    ... # código que manipula tokens
```

**Prós:**
- Poder máximo. Cobre todos os casos.
- Alinhado com ecossistema Rust.

**Contras:**
- Reescreveria metade do compilador.
- Lumina não tem fase separada de expansão — macros rodam no codegen.
- Fora de escopo para v1.x.

### Alternativa 5: Hygiene por convenção (`_` prefixo obrigatório)

Exigir que todo binding local de macro seja prefixado com `_`
(ex: `_tmp`, `_cond`). O parser rejeita `let tmp` dentro de
`quote:`.

**Prós:**
- Zero implementação.

**Contras:**
- Ergonomicamente ruim.
- Não evita colisão entre duas macros que ambas usam `_tmp`.
- Convenção é fácil de burlar (e o compilador não pega).

### Alternativa 6: Marcar `quote:` como escopo separado no semantic

Adicionar um flag `is_macro_scope` no analyzer. Durante a expansão,
bindings da macro são armazenados em um `scopes` separado e
consultados só em último caso.

**Prós:**
- Reusa a estrutura de `scopes` existente.

**Contras:**
- `_expand_macro_expr` roda no **codegen**, não no semantic. O
  semantic já terminou quando a macro é expandida.
- Reescrever a ordem das passadas (semantic → codegen) seria
  disruptivo.

## Decisão

Adotar **Alternativa 1 (alpha-renaming no `QuoteInterpreter`)** com
as seguintes regras:

### Regra 1: Bindings introduzidos por `quote:` são renomeados

Todo `VarDecl` dentro de `quote:` que **não** veio de `~x` recebe
nome único. O sufixo é `__<macro>_<name>_<counter>` — o contador é
por-instância de macro (uma por chamada de `quote:`).

```lumina
@macro
fn twice(x):
    quote:
        let tmp = ~x      # binding introduzido → __twice_tmp_1
        tmp + tmp         # referência → __twice_tmp_1 + __twice_tmp_1

fn main() -> int:
    let tmp = 42
    twice(tmp)            # tmp do call site NÃO é capturado
    return tmp            # 42
```

### Regra 2: `~x` preserva o nome

`UnquoteExpr` insere o nó do argumento **sem** renomear. Se o
argumento é `VariableExpr("tmp")`, o `tmp` continua `tmp`.

Isso permite que macros capturem variáveis do call site de forma
intencional:

```lumina
@macro
fn incrementa(var):
    quote:
        ~var = ~var + 1

fn main() -> int:
    mut x = 0
    incrementa(x)
    print(x)              # 1
    return 0
```

**Justificativa:** a decisão do usuário de escrever `~x` é
explícita. Ele sabe que `x` está sendo inserido no call site;
quer que resolva para o escopo do call site. Renomear seria
surpreendente.

### Regra 3: Símbolos livres referem-se ao call site

Se `quote:` contém `print(...)` e `print` não é um binding local,
ele permanece `print` — e resolve para o builtin no call site.

```lumina
@macro
fn log(msg):
    quote:
        print("LOG:", ~msg)

fn main() -> int:
    log("hello")
    return 0
```

`print` continua `print`; resolve para `BUILTIN_FUNCTIONS` no
codegen do call site.

**Nota:** Lumina não tem sistema de módulos com escopo léxico
completo. Implementar Hygiene total (Alternativa 2) só para
cobrir esse caso é over-engineering. Documentamos como
limitação conhecida.

### Regra 4: `gensym()` continua funcionando

`gensym("foo")` retorna `VariableExpr("__foo_N")`. Como o nome
já está mangled, o renaming da Regra 1 é no-op (`__foo_N` não
está no escopo de bindings, então não é tocado).

```lumina
@macro
fn swap(a, b):
    let tmp = gensym("swap_tmp")     # tmp = VariableExpr("__swap_tmp_1")
    quote:
        let ~tmp = ~a                 # ~tmp → VariableExpr("__swap_tmp_1")
        ~a = ~b
        ~b = ~tmp
```

Aqui, `~tmp` insere o `VariableExpr("__swap_tmp_1")` no `quote:`.
Como veio de unquote, **não é renomeado** (Regra 2). O nome
final é `__swap_tmp_1`. Sem colisão. Código existente continua
idêntico.

### Regra 5: Escape hatch — `quote_raw:`

Para casos onde hygiene automática atrapalha (macros que
deliberadamente querem introduzir nomes fixos — DSLs, `route!`),
oferecer `quote_raw:` que pula o renaming:

```lumina
@macro
fn route(method, path, handler):
    quote_raw:
        if ~method == "GET" and ~path == path:
            ~handler()
```

Aqui, `path` (fixo) é visível ao `handler`. Sem o `_raw`, o
`path` do `quote:` seria renomeado para `__route_path_1` e o
`handler` não o encontraria (a menos que use `~`).

**Documentação deve desencorajar `quote_raw:`** — 90% dos casos
devem usar `quote:`. O `quote_raw:` é uma saída de emergência
para quando a macro precisa se comportar como se fosse
"copiada e colada".

### Regra 6: Erros reportam o nome original

Se um binding renomeado causa erro em compile-time (tipo
incompatível, variável não usada, etc.), a mensagem mostra o
nome **original** (`tmp`), não o mangled (`__twice_tmp_1`).

O `QuoteInterpreter` mantém um `_rename_map: Dict[str, str]` que
mapeia `mangled → original`. Erros no codegen consultam esse
mapa ao formatar `LuminaError`.

### Regra 7: Macros aninhadas têm hygiene independente

Se `double(x)` chama `quad(x)` que por sua vez tem `quote:`, cada
expansão tem seu **próprio** contador e seu **próprio**
`_bound_names`. O `tmp` da `quad` e o `tmp` da `double` não
colidem.

```lumina
@macro
fn quad(x):
    quote:
        let t = ~x        # → __quad_t_1
        t + t + t + t

@macro
fn double(x):
    quote:
        let t = ~x        # → __double_t_1
        t + t

fn main() -> int:
    print(double(quad(5)))    # dois `t` distintos, sem colisão
    return 0
```

## Exemplos detalhados

### Exemplo A: `twice` canônico

**Entrada:**

```lumina
@macro
fn twice(x):
    quote:
        let tmp = ~x
        tmp + tmp

fn main() -> int:
    let tmp = 42
    print(twice(tmp))
    return tmp
```

**Expansão (pseudo-AST):**

```lumina
# call site
let tmp = 42
print(let __twice_tmp_1 = tmp
      __twice_tmp_1 + __twice_tmp_1)
return tmp
```

**Saída:**
```
84
```

### Exemplo B: `swap` com gensym (retrocompat)

**Entrada:**

```lumina
@macro
fn swap(a, b):
    let tmp = gensym("swap_tmp")
    quote:
        let ~tmp = ~a
        ~a = ~b
        ~b = ~tmp

fn main() -> int:
    mut x = 1
    mut y = 2
    swap(x, y)
    print(x, y)
    return 0
```

**Expansão:**

```lumina
# `tmp` da macro é `VariableExpr("__swap_tmp_1")`
# `~tmp` insere esse nó em quote: (Regra 2, não renomeia)
# resultado:
let __swap_tmp_1 = x       # (não `__swap___swap_tmp_1_1`!)
x = y
y = __swap_tmp_1
```

O renaming automático detecta que `__swap_tmp_1` não está em
`_bound_names` (porque veio de `~tmp`, não de um `VarDecl`
literal), então não toca. Comportamento idêntico ao atual.

**Saída:**
```
2 1
```

### Exemplo C: `quote_raw:` para DSL

**Entrada:**

```lumina
@macro
fn route(method, path, handler):
    quote_raw:
        if ~method == "GET" and path == ~path:
            ~handler()

fn main() -> int:
    route("GET", "/users", print("user route"))
    route("POST", "/users", print("NAO deve aparecer"))
    return 0
```

`quote_raw:` desliga o renaming. `path` no `quote:` permanece
`VariableExpr("path")` — e é inserido no escopo do call site.

**Expansão:**

```lumina
if "GET" == "GET" and path == "/users":
    print("user route")
```

`path` do call site precisa existir. Se não existir, erro de
"variável não declarada".

### Exemplo D: `@derive` generalizado (com hygiene)

**Entrada:**

```lumina
@derive(Eq, Debug)
struct Ponto:
    x: int
    y: int
```

**Expansão do `__eq__` (via `std/derives.lm`, ver ADR 0003 §"Fase 5"):**

```lumina
@macro
fn derive_eq(struct_name: str, fields: [str]) -> AstNode:
    let cond = quote: true
    let i = 0
    let n = len(fields)
    while i < n:
        let f = fields[i]
        let cmp = quote:
            a.~f == b.~f
        if i == 0:
            cond = cmp
        else:
            cond = quote:
                ~cond and ~cmp
        i += 1
    return quote:
        fn ~struct_name___eq__(a: ~struct_name, b: ~struct_name) -> bool:
            if ~cond:
                return true
            return false
```

Bindings: `cond`, `i`, `n`, `f`, `cmp`. Todos renomeados para
`__derive_eq_cond_1`, `__derive_eq_i_2`, etc. Sem colisão se
`derive_eq` for chamado múltiplas vezes (uma por struct).

## Consequências

### Positivas

- **Macros deixam de ser armadilha.** Colisões silenciosas viram
  impossíveis (a menos que o usuário use `quote_raw:`).
- **Reduz boilerplate em ~80%.** Macros não-triviais não precisam
  mais de `gensym` em cada binding.
- **Backwards-compatible.** Código com `gensym` continua funcionando.
- **Prepara `@derive` generalizado.** `std/derives.lm` pode gerar
  código sem poluir o namespace do usuário.
- **Erros com nome original.** `_rename_map` faz o reporter mostrar
  o nome humano.
- **Composável.** Macros aninhadas têm contadores independentes.

### Negativas

- **Superfície da linguagem cresce com `quote_raw:`.** Mais uma
  keyword. Mais um caminho para o usuário errar.
- **Erros em código gerado mais difíceis de ler.** Mensagens
  citam nomes originais via `_rename_map`, mas o IR final contém
  os mangled. Inspeção manual de `.ll` é mais trabalhosa.
- **Símbolos livres permanecem resolvidos no call site.** Hygiene
  total (Racket-style) não é o modelo. Documentar como limitação.
- **Colisão de mangling.** Dois bindings com mesmo nome na mesma
  macro são raros (o parser não permite dois `let x` no mesmo
  escopo, mas `for x` + `let x` seria raro), mas o contador
  resolve.
- **Performance de compilação.** O passe de coleta é O(AST da
  macro). Para macros grandes (derives), é da ordem de centenas
  de nós. Impacto ~microssegundos.

### Riscos

1. **`quote_raw:` vira regra em vez de exceção.** Usuários vão
   usar sempre que encontrarem dificuldade. Mitigação:
   documentação forte + `lumina lint` emite warning quando
   `quote_raw:` aparece sem `~` no escopo.

2. **Mangled names vazam para LSP/erros.** Se `_rename_map` não
   cobrir todos os caminhos de erro, o usuário vê
   `__twice_tmp_1` em uma mensagem. Mitigação: testes em
   `tests/test_macro_hygiene.py` cobrindo todos os tipos de erro
   (tipo incompatível, variável não usada, etc.).

3. **Interação com `@derive`.** Se o `@derive` migra para
   `std/derives.lm`, a expansão acontece no **semantic**, não no
   codegen. Hygiene implementada no `QuoteInterpreter` do codegen
   precisa ser replicada (ou reutilizada) no caminho do semantic.
   Mitigação: extrair a lógica de hygiene para um módulo
   compartilhado (`lumina/common/hygiene.py`).

4. **`gensym` e auto-hygiene colidem?** Se o usuário chama
   `gensym("tmp")` e depois tem `let tmp = ...` em `quote:`, os
   dois criam nomes diferentes (`__tmp_1` vs `__twice_tmp_1`).
   Sem colisão. OK.

5. **Performance de `_rename_map` em IR grande.** Um dict por
   expansão de macro. Para um arquivo com 1000 macros expandidas,
   são 1000 dicts pequenos. Memória desprezível.

## Implementação — fases

### Fase 1 — Coleta de bindings

**Arquivo:** `lumina/codegen/quote_eval.py`

Adicionar em `QuoteInterpreter.__init__`:

```python
def __init__(self, macros=None, macro_name="__anon"):
    self.env = {}
    self._gensym_counter = 0
    self._macros = macros or {}
    self._macro_name = macro_name
    self._hygiene_counter = 0
    self._bound_names = {}    # name → mangled
    self._rename_map = {}     # mangled → original (para erros)
```

Adicionar um passe `_collect_bindings(stmts)` que percorre a AST
da macro e popula `_bound_names` **antes** de qualquer build:

```python
def _collect_bindings(self, stmts):
    for stmt in stmts:
        self._collect_bindings_stmt(stmt)

def _collect_bindings_stmt(self, stmt):
    if isinstance(stmt, VarDecl):
        self._bind(stmt.name)
        if stmt.value:
            self._collect_bindings_expr(stmt.value)
    elif isinstance(stmt, ForStmt):
        self._bind(stmt.var_name)
        if stmt.index_var:
            self._bind(stmt.index_var)
        for s in stmt.body:
            self._collect_bindings_stmt(s)
    elif isinstance(stmt, IfStmt):
        for s in stmt.then_body:
            self._collect_bindings_stmt(s)
        for s in (stmt.else_body or []):
            self._collect_bindings_stmt(s)
    elif isinstance(stmt, (WhileStmt, DeferStmt)):
        for s in stmt.body:
            self._collect_bindings_stmt(s)
    # ... outros statements com body

def _bind(self, name):
    if name in self._bound_names:
        return
    self._hygiene_counter += 1
    mangled = f"__{self._macro_name}_{name}_{self._hygiene_counter}"
    self._bound_names[name] = mangled
    self._rename_map[mangled] = name
```

**Invariante:** `_collect_bindings` roda **uma vez** por
`interpret_expression`. Nunca durante o build (senão o counter
avança em cada lookup).

### Fase 2 — `_build_stmt` usa o mangled

Em `_build_stmt(VarDecl)`:

```python
if isinstance(stmt, VarDecl):
    original = self._coerce_name(stmt.name, stmt)
    mangled = self._bound_names.get(original, original)
    value = self._build_expr(stmt.value) if stmt.value is not None else None
    return VarDecl(mangled, stmt.var_type, value, stmt.is_mutable,
                   stmt.line, stmt.col)
```

Em `_build_stmt(ForStmt)`:

```python
if isinstance(stmt, ForStmt):
    var_name = self._bound_names.get(stmt.var_name, stmt.var_name)
    index_var = (self._bound_names.get(stmt.index_var, stmt.index_var)
                 if stmt.index_var else None)
    return ForStmt(
        var_name,
        self._build_expr(stmt.start) if stmt.start else None,
        self._build_expr(stmt.end) if stmt.end else None,
        self._build_expr(stmt.iterable) if stmt.iterable else None,
        [self._build_stmt(s) for s in stmt.body],
        index_var=index_var,
        elem_type=getattr(stmt, 'elem_type', None),
    )
```

Em `_build_expr(VariableExpr)`:

```python
if isinstance(expr, VariableExpr):
    mangled = self._bound_names.get(expr.name)
    if mangled is not None:
        return VariableExpr(mangled, expr.line, expr.col)
    return copy.deepcopy(expr)
```

**Ordem crítica:** `_collect_bindings` roda **antes** de
`_build_stmt` / `_build_expr`. Sem isso, `_build_expr(VariableExpr)`
não sabe que o nome é local.

### Fase 3 — `quote_raw:`

Adicionar `quote_raw` ao lexer (`TokenType.QUOTE_RAW`), nó
`QuoteRawExpr` na AST, e no `_build_quote` um parâmetro
`raw=False`:

```python
def _build_quote(self, stmts, raw=False):
    if raw:
        # Não renomeia
        return self._build_quote_impl(stmts, rename=False)
    return self._build_quote_impl(stmts, rename=True)
```

`QuoteRawExpr.statements` também é processado, mas com
`rename=False`.

### Fase 4 — Erros com nome original

Adicionar ao `LLVMCodegen` um atributo `_macro_rename_maps: Dict[int, Dict[str, str]]`
(chave = id do nó ou hash). Ao emitir `LuminaError` para um nó
gerado por macro, traduzir os nomes via mapa.

**Alternativa mais simples:** o `QuoteInterpreter` injeta o
mangled e o original no próprio nó (`node.original_name = "tmp"`).
O `LuminaError` formatter consulta `getattr(node, 'original_name', node.name)`.

### Fase 5 — Deprecar `gensym` (soft)

Emitir warning `W006` do `lumina lint` se `gensym()` for chamado
em macro nova (a partir de v1.1). Manter funcional
indefinidamente.

**Motivo:** `gensym` manual é permitido e útil para casos onde o
usuário quer controle explícito (e.g., passar o nome mangled
para outra macro). Não remover.

### Fase 6 — Testes

**Arquivo:** `tests/test_macro_hygiene.py`

Cobre:
- `twice` com `tmp` no call site → não colide
- Duas invocações de `twice` no mesmo escopo → slots distintos
- `incrementa(x)` com `~x` → captura o `x` do call site
- `quote_raw:` expõe nome fixo
- `swap` com `gensym` → retrocompatibilidade
- Erros mostram nome original
- Macros aninhadas (`double(quad(5))`) → counters independentes
- `@derive` generalizado gera AST limpa

## Perguntas abertas

1. **Formato do mangled.**
   - `__twice_tmp_1` — curto, evita `::` no LLVM.
   - `twice::tmp#1` — qualificado, estilo Racket.
   - **Decisão:** `__twice_tmp_1`. Simples, e `__` já é usado
     por `gensym`.

2. **Counter é por-instância ou global?**
   - Por-instância (uma por `interpret_expression`). Nomes ficam
     curtos e determinísticos para uma mesma macro. Duas
     invocações geram `__twice_tmp_1` **idêntico** — o que é
     problemático se ambas vão para o mesmo escopo?
   - **Decisão:** por-instância. O codegen de cada call site
     emite o IR em um contexto isolado (novo `alloca` por
     chamada), então dois `__twice_tmp_1` em call sites
     diferentes não colidem no LLVM (SSA renomeia).
   - **Verificar:** se dois `quote:` viram parte do mesmo bloco
     IR, o `alloca` do segundo sombreia o do primeiro. Isso
     **não é bug** — é o comportamento esperado de escopos
     lineares. Mas convém testar.

3. **`quote:` em tipo (`quote_type:`) — hygiene se aplica?**
   - Adiado. `quote_type:` ainda não existe (v1.0).

4. **`~@xs` em statement position — hygiene se aplica aos
   statements espalhados?**
   - Sim, se eles introduzem bindings. O `_collect_bindings` deve
     visitar o array resultante.
   - Requer que `~@xs` esteja implementado (v0.9.x). Bloqueado por
     isso.

5. **`@derive` migrado para `std/derives.lm` — como o hygiene
   atravessa semantic → codegen?**
   - Extrair `_collect_bindings` e `_bound_names` para
     `lumina/common/hygiene.py`, usado por ambos os
     interpretadores.
   - Trabalho para v1.2.

6. **`gensym` dentro de `quote_raw:`?**
   - `gensym` continua funcionando. `quote_raw:` só desliga o
     renaming **automático**; `gensym` continua explícito.

7. **Como testar performance de compilação?**
   - Micro-benchmark: `time lumina build` num arquivo com 1000
     invocações de macro. Baseline atual não tem esse teste.
     Adicionar em `benchmarks/` (opcional).

## Referências

- **Racket `syntax-rules`** — hygiene total, escopos léxicos
  (Flatt, *Composable and Compilable Macros*, ICFP 2002).
- **Clojure `syntax-quote`** — hygiene parcial via `syntax-quote`
  + `~`, com `foo#` para gensym automático.
- **Nim `quote do:`** — hygiene automática por padrão; nomes
  internos viram mangled.
- **Rust `macro_rules!`** — hygiene por "syntax context"
  (identificadores carregam contexto de expansão); o mais próximo
  do design proposto.
- **Elixir `quote do:`** — hygiene via contexto de macro
  (`unquote` / `unquote_splicing`).
- **Scheme `syntax-case`** — sistema avançado de hygiene com
  `datum->syntax` como escape.
- **Hygienic Macros: Why They're Important** (Kohlbecker et al.,
  1986) — paper clássico sobre o problema.

## Aprovação

| Revisor | Status | Data |
|---|---|---|
| (a preencher) | | |

---

## Apêndice A — Comparação com ADRs anteriores

| Sistema | Hygiene | `gensym` | Escape hatch |
|---|---|---|---|
| ADR 0003 (v0.9) | Manual | Obrigatório | — |
| **ADR 0004 (v1.1)** | **Automática** | Opcional | `quote_raw:` |
| Racket | Automática total | Não existe | `datum->syntax` |
| Clojure | Automática parcial | `foo#` | `quote` (sem syntax) |
| Rust `macro_rules!` | Automática | Não existe | `$crate` |

## Apêndice B — Exemplo end-to-end

**Código do usuário:**

```lumina
@macro
fn safe_div(a, b):
    quote:
        let denom = ~b
        if denom == 0:
            print("divisao por zero")
            0
        else:
            ~a / denom

fn main() -> int:
    let denom = 10      # nome no call site
    print(safe_div(100, denom))
    print(safe_div(5, 0))
    return 0
```

**Passo 1 — coleta de bindings:**

`_collect_bindings` percorre `[VarDecl('denom', ...), IfStmt(...)]`
e popula:
- `_bound_names["denom"] = "__safe_div_denom_1"`
- `_rename_map["__safe_div_denom_1"] = "denom"`

**Passo 2 — build:**

```python
# VarDecl → VarDecl("__safe_div_denom_1", value=UnquoteExpr(b))
# VariableExpr("denom") → VariableExpr("__safe_div_denom_1")
# BinaryExpr('/', a_unquoted, VariableExpr("__safe_div_denom_1"))
```

**Passo 3 — expansão no call site:**

```lumina
# Primeira chamada
let __safe_div_denom_1 = denom       # RHS: `denom` do call site (10)
if __safe_div_denom_1 == 0:
    print("divisao por zero")
    0
else:
    100 / __safe_div_denom_1          # 100/10 = 10

# Segunda chamada (novo escopo, mesmo mangled)
let __safe_div_denom_1 = 0
if __safe_div_denom_1 == 0:
    print("divisao por zero")         # dispara
    0
else:
    5 / __safe_div_denom_1
```

O `denom` do call site (10) é passado via `~b`. O binding
interno (`__safe_div_denom_1`) é invisível fora da macro.

**Saída:**
```
10
divisao por zero
0
```

## Apêndice C — Glossário

- **Hygiene** — propriedade de uma macro de não introduzir
  bindings que colidem com o call site.
- **Alpha-renaming** — renomear variáveis ligadas para nomes
  frescos (conceito do cálculo lambda).
- **Gensym** — gerador de símbolos únicos; usado para hygiene
  manual.
- **Escopo léxico** — regra de resolução de nomes baseada em
  onde a variável foi **definida** (não onde é usada).
- **Escopo dinâmico** — regra de resolução baseada em onde o
  código está **executando** no momento.
- **Binding introduzido** — variável declarada pela macro
  (visível apenas dentro dela).
- **Símbolo livre** — referência que **não** é resolvida por um
  binding da macro; resolve no escopo externo (call site).
- **Mangled name** — nome codificado/transformado para evitar
  colisão (`__twice_tmp_1`).
- **Call site** — local onde a macro é invocada.
- **Escape hatch** — mecanismo para desligar hygiene automática
  quando ela atrapalha.

## Apêndice D — O que NÃO muda

Para deixar explícito:

1. **`quote:` sem bindings locais continua idêntico.**
   ```lumina
   quote:
       print("hello")
   ```
   `print` é símbolo livre. Não renomeado.

2. **`~x` continua preservando o nome.**
   ```lumina
   quote:
       ~user_var
   ```
   `user_var` é inserido como está.

3. **`gensym()` continua funcionando.**
   ```lumina
   let tmp = gensym("x")
   quote:
       let ~tmp = 1
   ```
   O `~tmp` insere `VariableExpr("__x_1")`. Não renomeado.

4. **Macros de expressão (`return quote: ~x`) continuam iguais.**
   Se não há `let` no corpo, não há binding para renomear.

5. **`@derive` atual (Python) não é afetado.**
   O `DerivesMixin._expand_derives` gera nomes `Ponto___eq__`
   diretamente. Se migrar para `std/derives.lm` (v1.2), o
   hygiene se aplica aos bindings **internos** dos métodos
   (`result`, `p`, `a`, `b`), não aos nomes dos métodos.

---

**Fim da ADR 0004.**