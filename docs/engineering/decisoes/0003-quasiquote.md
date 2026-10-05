---
status: proposto
data: 2026-10-03
autores: [Adam Gabriel]
revisores: []
---

# ADR 0003 — Macros com quasiquote

## Resumo

Introduz **quasiquote** (`quote:`) como primitiva de construção de AST
em compile-time. Permite que macros `@macro` gerem nós sintáticos novos
— não apenas substituam parâmetros por argumentos. É a peça que falta
para macros de verdade em Lumina (similar a `quote!` do Rust, `~` do
Clojure, ou backtick Lisp).

## Contexto

### Estado atual

Macros em Lumina (v0.6.0+) são **substituição de texto sobre a AST**:

```lumina
@macro
fn dobro(x: int) -> int:
    return x * 2

fn main() -> int:
    print(dobro(5))    # vira (5) * 2
```

A expansão é:
1. Parser lê `@macro` como `Function` com attr `macro`.
2. `codegen_user_call` detecta o nome em `self.macros`.
3. `_expand_macro_expr` substitui `VariableExpr("x")` pelo nó do
   argumento.
4. Codegen emite IR do nó substituído.

### Limitações

**Limitação 1: não constrói nós novos.**

O corpo da macro só pode referenciar os próprios parâmetros. Não há
como criar um `IfStmt`, `MatchStmt`, ou `ForStmt` que o chamador
não escreveu.

```lumina
# Impossível hoje:
@macro
fn unless(cond, body):
    return if not cond:
        body
```

A expansão `if not ~cond: ~body` requer que o compilador construa um
`IfStmt` novo com `condition = UnaryExpr('not', cond_arg)` e
`then_body = [body_arg]`. Substituição de texto não faz isso.

**Limitação 2: sem repetição.**

Não há `~@xs` para espalhar uma lista de statements:

```lumina
@macro
fn trace_vars(names):
    for n in names:
        print(n, "=", n)   # não expande para múltiplos prints
```

**Limitação 3: sem controle de escopo.**

Macros introduzem bindings que colidem com o call site:

```lumina
@macro
fn twice(x):
    let tmp = x
    print(tmp)
    print(tmp)
    return tmp

fn main() -> int:
    let tmp = 42
    twice(tmp)    # `tmp` da macro colide com `tmp` do usuário
    return tmp    # qual `tmp`?
```

Hoje, o codegen pode produzir IR inválido ou comportamento
surpreendente. Não há higiene.

### Casos de uso almejados

1. **`unless` / `until` / `loop N times`** — construções de controle
   de fluxo que a linguagem não tem, mas que macros podem gerar.

2. **Derivação de boilerplate** — `@derive(Serialize, Deserialize)`
   já existe via AST synthesis hardcoded em
   `lumina/semantic/derives.py`. Generalizar isso com quasiquote
   permitiria derives definidos pelo usuário.

3. **Asserções ricas** — `assert_eq!(a, b)` que imprime os dois
   lados em caso de falha, gerando `if a != b: print(a, b, "!="); abort()`
   inline.

4. **Roteamento HTTP** — `route!("GET /users/:id", handler)` que
   gera o parsing de path em compile-time.

5. **DSLs** — uma API de "builder" que hoje exige runtime pode virar
   compilação pura.

### Requisitos

1. **Expressividade suficiente** para os 5 casos acima.
2. **Sintaxe que case com Lumina** (indentação significativa, sem `;`).
3. **Sem ambiguidade** com `$"..."` (f-strings) ou outros sigilos.
4. **Hygiene:** macros não devem introduzir bindings que colidem
   silenciosamente com o call site.
5. **Erros em compile-time:** AST gerado inválido deve falhar com
   mensagem apontando para o uso da macro, não para linhas internas.
6. **Zero runtime overhead:** a expansão é 100% compile-time.
7. **Composável:** uma macro pode gerar código que chama outra macro.

## Alternativas consideradas

### Alternativa 1: Rust-style `quote:`

```lumina
@macro
fn unless(cond, body):
    quote:
        if not ~cond:
            ~body
```

- `quote:` abre bloco de construção de AST.
- `~expr` insere o nó de `expr` no ponto.
- `~@stmts` espalha uma lista de statements.

**Prós:** familiar para devs Rust; `~` é sigilo distinto; multi-linha
natural; `quote:` casa com blocos `:` do Lumina.

**Contras:** `~` é usado como unário (bitwise NOT) na expressão
`~x`. Precisa desambiguar por contexto — dentro de `quote:`, `~`
significa "unquote"; fora, é bitwise NOT. Resolvível pelo parser
(contexto de `quote:`) mas requer cuidado.

### Alternativa 2: Lisp-style backtick

```lumina
@macro
fn unless(cond, body):
    `(if (not ~cond) ~body)
```

**Prós:** familiar para devs Lisp/Scheme/Clojure; notação compacta.

**Contras:** sintaxe S-expression é estranha em linguagem com
indentação. Exigiria uma mini-linguagem de S-expr só para macros.

### Alternativa 3: `$$` templates com `$`-prefix

```lumina
@macro
fn unless(cond, body):
    return $$
        if $cond:
            $body
    $$
```

**Prós:** prefixo único, sem ambiguidade com `~` unário.

**Contras:** `$"..."` já usa `$` para interpolação. Duas semânticas
do mesmo sigilo confundem.

### Alternativa 4: AST-builder API

```lumina
@macro
fn unless(cond, body):
    return IfStmt(UnaryExpr("not", cond), body, None)
```

**Prós:** explícito, sem sintaxe nova; tudo é código normal.

**Contras:** extremamente verboso. Cada macro é uma árvore de
construtores. Não escala para macros de mais de 5 linhas.

### Alternativa 5: Não fazer nada

Manter macros como substituição de texto.

**Prós:** zero risco.

**Contras:** limitação permanente; macro não pode construir nada
novo; `@derive` continua hardcoded.

## Decisão

Adotar **Alternativa 1 (`quote:` + `~` + `~@`)** com as seguintes
regras:

### Sintaxe

1. **`quote:` em posição de expressão** — retorna um nó de AST.

   ```lumina
   let node = quote:
       let x = 1
       x + 2
   ```

   Retorna um `BlockExpr` com `statements = [VarDecl, ...]` e
   `final_expr = BinaryExpr('+', ...)`.

2. **`quote:` em posição de statement** — inlineia o bloco gerado.

   ```lumina
   @macro
   fn unless(cond, body):
       quote:
           if not ~cond:
               ~body
   ```

   Como o corpo da macro é `quote:`, a expansão inlineia o
   `IfStmt` gerado no call site.

3. **`~expr`** — unquote de expressão. Insere o nó de `expr` no
   ponto. `expr` é avaliada em compile-time: é um valor de tipo
   `AstNode`.

   ```lumina
   quote:
       print(~some_expr)
   ```

   Substitui `~some_expr` pelo nó que `some_expr` avalia.

4. **`~@expr`** — unquote-splice. `expr` deve ser `[AstNode]`;
   os nós são espalhados.

   ```lumina
   quote:
       ~@prelude_stmts
       print("done")
   ```

5. **`gensym()` builtin** — gera nome único.

   ```lumina
   @macro
   fn swap(a, b):
       let tmp_name = gensym("tmp")
       quote:
           let ~tmp_name = ~a
           ~a = ~b
           ~b = ~tmp_name
   ```

   `gensym` retorna um `str` que o parser reconhece como binding
   novo quando interpolado em posição de declaração.

### Tipos de AST em compile-time

Uma macro recebe parâmetros de tipo `AstNode` (implícito). O corpo
da macro:

- Pode chamar `gensym(name)` → `str`.
- Pode inspecionar o nó: `~x.kind`, `~x.children` (leitura).
- Pode retornar `quote:` ou código normal.

**Novos tipos introduzidos:**

```
AstNode    — nó de AST opaco
AstKind    — enum: Expr, Stmt, Pattern, ...
```

Ambos são **compile-time only** — não podem vazar para runtime.
Erro se macro tentar retornar um `AstNode` de uma função `fn(...) -> T`.

### Hygiene

**v1 (esta ADR): manual.**

- O usuário é responsável por usar `gensym()` para bindings internos.
- `~x` preserva `x` exatamente como aparece no call site.
- Sem renomeação automática.

**v2 (futuro): automática por padrão.**

- Bindings introduzidos por `quote:` recebem nomes mangled
  automaticamente.
- `~x` continua preservando o nome.
- Escape hatch `quote_raw:` desliga hygiene.

Razões para começar manual:

1. Renomeação automática exige análise de escopo durante a expansão —
   trabalho complexo que pode ser adiado.
2. Macros em v1 são usadas principalmente por usuários avançados que
   entendem o problema.
3. Ir de manual para automática é backwards-compatible; o contrário não.

### Erros

Erros em AST gerado apontam para o **call site**, não para linhas
internas da macro:

```
erro: `if` exige condição `bool`
  --> main.lm:15:5
   |
15 |     unless(x, ...)
   |     ^^^^^^ macro `unless` expandida aqui
   |
   = nota: nó `if` gerado por `unless` em macro.lm:3
```

O compilador mantém um **call stack** de expansões de macro para
reconstruir a trace.

### Sintaxe `~` vs bitwise NOT

Fora de `quote:`, `~x` é bitwise NOT (int). Dentro de `quote:`, `~x`
é unquote. O parser desambigua por contexto — não há ambiguidade
porque `quote:` é um token explícito.

Dentro de um bloco `quote:` que contém `quote:` aninhado, `~` se
refere ao **quote mais interno**. Não há nesting de unquote.

## Consequências

### Positivas

- **Macros de verdade.** `unless`, `assert_eq!`, `route!`, DSLs — todos
  viáveis.
- **`@derive` generalizável.** Derives definidos pelo usuário viram
  macros; `std/derives.lm` pode substituir `lumina/semantic/derives.py`.
- **Redução de boilerplate.** Padrões repetitivos podem ser fatorados.
- **Preparação para self-hosting.** O parser em `.lm` usará macros
  para reduzir duplicação (parsing de expressão é famoso por isso).
- **Sintaxe familiar.** Devs Rust reconhecem `~`/`~@` como `$`/`$@`
  de `quote!`; devs Lisp reconhecem a estrutura.

### Negativas

- **Complexidade no parser.** `~` muda de significado dentro de
  `quote:`. Dois contextos precisam ser mantidos.
- **Complexidade no codegen.** Expansão de macro não é mais uma
  simples substituição; envolve avaliar o corpo da macro em
  compile-time e materializar o AST resultante.
- **Erros mais difíceis de reportar.** Mensagens devem apontar para
  call site e para o ponto da macro que gerou o nó.
- **Risco de abuso.** Quasiquote permite gerar código arbitrariamente
  complexo. Documentação precisa educar sobre quando **não** usar.
- **`gensym` + hygiene manual** é uma fonte de bugs silenciosos
  quando o usuário esquece.

### Riscos

1. **`~` como overload de bitwise NOT.** Mitigado por contexto. Se
   em algum caso-limite o parser errar, o teste de regressão falha.

2. **Performance de compilação.** Cada expansão pode envolver
   re-parse + re-analyze do bloco `quote:`. Mitigação: cachear o AST
   da macro após a primeira análise, só substituir nós.

3. **Interação com `comptime`.** `comptime(expr)` já avalia
   expressões em compile-time. `quote:` é ortogonal: avalia AST, não
   valor. Documentar a distinção.

4. **Ambiguidade com pattern matching.** `~` poderia ser confundido
   com "não" em pattern. Hoje `not` é keyword, então não há conflito.
   Mas se um dia `!` for introduzido como negação, o conflito existe.

## Implementação — fases

### Fase 1 — Parser reconhece `quote:`, `~`, `~@`

**Arquivos:**
- `lumina/lexer/tokens.py` — adicionar `TILDE_UNQUOTE` (ou reusar
  `TILDE` com contexto).
- `lumina/parser/expressions.py::parse_factor` — detectar `quote:`.
- `lumina/parser/expressions.py::parse_unary` — detectar `~expr` e
  `~@expr` dentro de `quote:`.
- `lumina/ast/expressions.py` — novos nós `QuoteExpr`, `UnquoteExpr`,
  `UnquoteSpliceExpr`.

**Entregável:** `quote:` parseia, mas codegen ainda não expande.

### Fase 2 — Codegen constrói `AstNode` em compile-time

**Arquivos:**
- `lumina/codegen/expressions/macros.py` — `_expand_macro_expr` agora
  avalia `quote:` como construção de AST.
- Novo módulo `lumina/codegen/ast_constructors.py` — mapeia
  `(kind, args)` → nó AST.

**Entregável:** `@macro fn id(x): return quote: ~x` compila.

### Fase 3 — `gensym` e hygiene manual

**Arquivos:**
- `lumina/builtins.py` — registrar `gensym` como builtin
  compile-time.
- `lumina/codegen/expressions/builtins.py` — emitir nome único.

**Entregável:** `@macro fn swap(a, b)` funciona sem colisão.

### Fase 4 — Erros com call stack

**Arquivos:**
- `lumina/errors.py` — adicionar `macro_stack: List[MacroFrame]`.
- `lumina/codegen/expressions/macros.py` — push/pop do stack durante
  expansão.
- `lumina/errors.py::format_error` — renderizar stack.

**Entregável:** erros em macros apontam para o call site.

### Fase 5 — Migração de `@derive`

**Arquivos:**
- `std/derives.lm` — reimplementa `Eq`, `Debug`, `Clone`, `Default`
  em Lumina usando quasiquote.
- `lumina/semantic/derives.py` — mantém fallback hardcoded por
  compat; delega para `std/derives.lm` se disponível.

**Entregável:** `@derive` extensível pelo usuário.

### Fase 6 — Hygiene automática (v2)

Adiada. Requer alpha-renaming durante expansão.

## Perguntas abertas

1. **`quote:` ou `quote!`?** `quote:` casa com blocos `:` do Lumina;
   `quote!` casa com macros `nome!(args)`. Decisão: **`quote:`**
   (mais consistente com a linguagem).

2. **`~@` deve aceitar `[AstNode]` ou qualquer iterável?** Decisão:
   **`[AstNode]`** apenas. Evita complexidade desnecessária em v1.

3. **`gensym` retorna `str` ou `Ident`?** Decisão: **`str`**. É mais
   simples — `Ident` seria um tipo novo só para isso.

4. **Quasiquote em tipo também?** `quote_type:` para gerar `TypeNode`?
   Adiado. Se necessário, v2.

5. **Macros podem inspecionar o AST recebido?** `~x.kind` para
   pattern matching sobre nós? Adiado. v1 só substitui.

6. **Interação com `@macro` statement-level?** `nome!(args)` continua
   funcionando. `quote:` é ortogonal — pode aparecer dentro de
   qualquer macro.

7. **Como `quote:` interage com captura de variáveis do escopo
   externo?** Um `quote:` dentro de `fn main` que referencia `x`
   captura `x` por referência? Decisão: **captura por referência,
   como closures** — `~x` é o que traz valor; `x` dentro do `quote:`
   é o `VariableExpr("x")` do escopo externo.

## Exemplos

### Exemplo 1: `unless`

```lumina
@macro
fn unless(cond: bool, body):
    quote:
        if not ~cond:
            ~body

fn main() -> int:
    let x = 10
    unless(x > 5, print("x pequeno"))
    return 0
```

Expansão (AST):
```lumina
if not (x > 5):
    print("x pequeno")
```

### Exemplo 2: `swap` com `gensym`

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
    swap!(x, y)
    print(x, y)   # 2 1
    return 0
```

### Exemplo 3: `assert_eq!` com trace

```lumina
@macro
fn assert_eq(a: int, b: int):
    quote:
        if ~a != ~b:
            print("assert_eq falhou: ", ~a, " != ", ~b)
            abort()
        else:
            print("assert_eq OK")

fn main() -> int:
    assert_eq!(1 + 1, 2)
    return 0
```

### Exemplo 4: `repeat N times`

```lumina
@macro
fn repeat(n: int, body):
    let i = gensym("i")
    quote:
        mut ~i = 0
        while ~i < ~n:
            ~body
            ~i = ~i + 1

fn main() -> int:
    repeat!(3, print("hello"))
    return 0
```

### Exemplo 5: `route` DSL

```lumina
@macro
fn route(method: str, path: str, handler):
    let path_var = gensym("path")
    quote:
        if ~method == "GET" and ~path == ~path_var:
            ~handler()
```

## Referências

- **Rust `quote!`** — `quote::quote!` produz `proc_macro2::TokenStream`;
  `~` não existe (usa `#`); macro é procedural, não sintática.
- **Clojure `syntax-quote`** — `` `(...) `` com `~` e `~@`; higiênico
  por padrão com `foo#` para gensym automático.
- **Scheme `quasiquote`** — `` `(...) `` com `,` e `,@`; não
  higiênico; `gensym` manual.
- **Nim `quote do:`** — sintaxe indentada similar; higiene por padrão.
- **Julia `:(...)`** — `quote ... end`; `$(...)` para interpolação.
- **Racket `syntax-parse`** — sistema avançado de hygiene automática.

## Aprovação

| Revisor | Status | Data |
|---|---|---|
| (a preencher) | | |

---

## Apêndice A — Comparação de sintaxe

| Linguagem | Abre quote | Unquote | Splice | Hygiene |
|---|---|---|---|---|
| Lisp | `` ` `` | `,` | `,@` | manual |
| Clojure | `` ` `` | `~` | `~@` | automática |
| Scheme | `` ` `` | `,` | `,@` | manual |
| Rust | `quote! { }` | `#x` | `#(#xs)*` | automática |
| Julia | `quote ... end` | `$x` | `$(xs...)` | manual |
| Nim | `quote do:` | — | — | automática |
| **Lumina (proposto)** | `quote:` | `~x` | `~@xs` | manual (v1) |

## Apêndice B — IR de expansão

Quando o codegen encontra `nome(args)` e `nome` é macro:

1. Parser já produziu `CallExpr(callee=nome, args)`. Não há mudança.

2. Semantic resolve `nome` para `Function` com attr `macro`. Marca
   `CallExpr` como macro-call (novo `is_macro_call: bool`).

3. Codegen de `CallExpr`:
   - Se `is_macro_call`:
     - Salva o `MacroFrame` (call site, nome).
     - Avalia `macro.body` com os parâmetros ligados aos nós de
       `args`.
     - Resultado: um `AstNode`.
     - Substitui o `CallExpr` pelo nó gerado e re-visita.
   - Senão: caminho normal.

4. Um `QuoteExpr` no corpo da macro **constrói** o `AstNode`:
   - Para cada filho direto, se for `UnquoteExpr`, avalia o valor
     (que é `AstNode`) e insere.
   - Se for `UnquoteSpliceExpr`, avalia (que é `[AstNode]`) e
     concatena.
   - Senão, recursivamente constrói.

5. O `AstNode` resultante é então processado normalmente pelo
   codegen (validações semânticas re-aplicadas, monomorphization,
   etc.).

## Apêndice C — Glossário

- **Quasiquote** — operador que constrói uma estrutura que *parece*
  código, com escapes para interpolar.
- **Unquote** — dentro de um quasiquote, avalia a expressão e insere
  o valor.
- **Unquote-splice** — unquote que espalha múltiplos elementos.
- **Hygiene** — propriedade de uma macro de não introduzir bindings
   que colidem com o call site.
- **Gensym** — gerador de símbolos únicos; usado para hygiene manual.
- **Macro frame** — entrada da call stack de expansão, usada para
   reportar erros.

---

**Fim da ADR 0003.**