# Changelog

Todas as mudanças relevantes do **Lumina** são documentadas neste arquivo.

O formato segue, de forma geral, as convenções do [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e o projeto segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [1.0.0] — 2026-09-25

> **Milestone:** primeira versão estável. Fecha as lacunas do v0.9.0
> (bytes/copy), conserta bugs de borda em slices e parser self-hosted,
> e documenta a decisão de hygiene automática (ADR 0004).

### ✨ Adicionado

* `bytes(s: str) -> [int]` — view imutável da string como bytes.
* `copy(s: [T]) -> [T]` — cópia profunda com backing buffer próprio.
* ADR 0004 — hygiene automática em macros (design para v1.x).
* `lumina_core/parser.lm` — corrigidos 4 bugs bloqueantes para self-hosting.

### 🐛 Corrigido

* `CompoundAssignStmt` em slice fazia GEP no `%Slice_T_*` em vez do `.data`.
* `_expect_gt_for_type` (parser.lm) não splittava `>>` (fecha `Vec<Vec<T>>`).
* `parse_switch` (parser.lm) re-consumia `T_MATCH`.
* `tokenize` (parser.lm) era stub com struct não inicializada.
* `node_nexts` era usado como sibling chain **e** campo específico.

---

## [0.9.0] — 2026-09-25

> **Milestone:** quasiquote (`quote:` / `~` / `~@`) — macros de verdade.

Esta versão introduz **quasiquote** como primitiva de construção de
AST em compile-time. Macros `@macro` deixam de ser apenas substituição
de texto — podem gerar nós sintáticos novos (`if`, `match`, `for`,
declarações) que o chamador não escreveu.

### ✨ Adicionado

#### `quote:` — construção de AST

* Nova construção `quote:` permite que macros `@macro` construam
  nós de AST:

  ```lumina
  @macro
  fn unless(cond, body):
      quote:
          if not ~cond:
              ~body

  fn main() -> int:
      let x = 10
      unless(x > 100, print("pequeno"))
      return 0
  ```

* Forma multi-linha (bloco indentado) e single-line (`quote: ~x`)
  suportadas.
* Um `quote:` com múltiplos statements produz um `BlockExpr` que
  preserva `final_expr` (a última expressão) como valor.

#### `~x` — unquote

* Dentro de `quote:`, `~x` insere o AST de `x` no ponto.
* `x` é avaliado em compile-time. Pode ser:
  * um parâmetro da macro (nó de AST ligado ao argumento);
  * uma variável local da macro;
  * o resultado de `gensym(...)`;
  * o resultado de uma chamada a outra macro.

#### `~@xs` — unquote-splice

* Espalha uma lista de nós: `~@stmts` em posição de statement, ou
  `~@elems` dentro de `[...]`.
* Requer que `xs` avalie para `[AstNode]` (lista de nós).

#### `gensym(name)` — geração de nomes únicos

* Builtin compile-time dentro de macros.
* Retorna `VariableExpr` com nome mangled (`__name_N`).
* Uso típico para hygiene manual:

  ```lumina
  @macro
  fn swap(a, b):
      let tmp = gensym("tmp")
      quote:
          let ~tmp = ~a
          ~a = ~b
          ~b = ~tmp
  ```

#### Interpretador em compile-time

* Novo módulo `lumina/codegen/quote_eval.py` — `QuoteInterpreter`.
* Avalia o corpo da macro em compile-time, misturando:
  * **valores Python** (int, float, bool, str) quando o resultado é
    computável (`1 + 2` → `3`);
  * **nós de AST** quando o resultado depende de argumentos.
* Fast-path para corpos de um único `return <expr>`.
* Suporta `let`, `if`, `while`, `return`, `assign` como scaffolding
  dentro do corpo da macro.
* Erro com mensagem clara (`QuoteError`) se o corpo usar construções
  não suportadas.

#### Expansão recursiva de macros aninhadas

* Uma macro pode chamar outra dentro do corpo, e a expansão é
  recursiva:

  ```lumina
  @macro
  fn dobro(x):
      return x * 2

  @macro
  fn quadruplo(x):
      return dobro(dobro(x))
  ```

* `QuoteInterpreter(macros=...)` recebe o dicionário de macros do
  compilador; ao encontrar `CallExpr` cujo callee é uma macro, expande
  recursivamente.

#### Parâmetros de macro sem anotação de tipo

* Parâmetros de `@macro` podem ser declarados sem `: T`:

  ```lumina
  @macro
  fn unless(cond, body):     # sem tipo
      quote: ...
  ```

* Semantic trata `"auto"` como type param — aceita qualquer coisa.
* Parâmetros com anotação continuam funcionando.

### 🔧 Alterado

#### `_expand_macro_expr` usa `QuoteInterpreter`

* Macros de expressão deixam de fazer substituição textual
  (`_substitute_in_expr`) e passam a interpretar o corpo via
  `QuoteInterpreter`.
* Substituição direta continua funcionando — o interpretador
  generaliza o comportamento anterior.
* Comportamento de `return quote:` no top-level do corpo é
  equivalente a `quote:` isolado.

#### Semantic pula corpos de macro

* `SemanticAnalyzer.analyze` não analisa mais o corpo de funções
  com atributo `@macro`.
* Justificativa: usam `quote:` / `~` / `~@` / `gensym` — construções
  que **não têm semântica de runtime**. O AST gerado pela expansão
  é analisado normalmente no call site.

#### Formatter preserva `quote:` / `~` / `~@`

* `format_node` reconhece `QuoteExpr`, `UnquoteExpr`,
  `UnquoteSpliceExpr` e reemite a sintaxe corretamente.
* Round-trip `fmt(fmt(x)) == fmt(x)` mantido.

#### Parser — `~` como bitwise NOT fora de quote

* Fecha gap antigo: o lexer emitia `TILDE` mas o parser não parseava.
* Fora de `quote:` (`_in_quote_depth == 0`), `~x` é `UnaryExpr('~', x)`
  → bitwise NOT.
* Dentro de `quote:`, `~x` é unquote.
* Codegen de `~x` (bitwise NOT) implementado em
  `visit_UnaryExpr` (`self.builder.not_`).

#### LSP autocompleta `quote`

* Adicionada keyword `quote` à lista de completions.

### 🐛 Corrigido

#### `visit_SliceExpr` — `is_string` não computado

* A versão inicial referenciava `is_string` antes de definir,
  disparando `UnboundLocalError` em todo `v[a..b]`. Corrigido
  computando `is_string` imediatamente após `arr_val = visit(...)`.

#### `visit_MemberExpr` (semantic) — slices sem campos

* `s.len` e `s.data` falhavam com "Tipo '[int]' não é uma
  Struct/Enum". Adicionado caso explícito para slices.

#### `_infer_for_elem_type` — slices não reconhecidos

* `for x in v[..]` caía no fallback `int`. Adicionado caso
  `[T]` → `T`.

#### `visit_AssignStmt` — `s[i] = v` em slice

* Atribuição via index em slice exigia extrair `.data` antes do
  GEP. Sem isso, `s[0] = 42` escrevia no `%Slice_T_*` em vez de no
  buffer de dados.

#### `_eval(VariableExpr)` retornava nó literal sem unbox

* `if flag > 0` no corpo da macro construía um `BinaryExpr` em vez
  de computar — nós de AST são truthy, então o `if` sempre tomava
  o ramo `then`. Adicionado `_unbox` que converte literais AST
  (`NumberExpr("1")` → `1`, `BoolExpr(True)` → `True`, etc.) em
  valores Python.

#### `_build_expr(UnquoteExpr)` retornava primitivo Python

* `quote: let tmp = ~x` onde `x` é ligado a um literal produzia
  `VarDecl(value=21)` — o codegen não tem `visit_int`, e o valor
  virava `0`. Corrigido com `_to_ast()` envolvendo primitivos.
* Invariante documentado: `_build_expr` sempre retorna nó de AST;
  `_eval` é quem lida com primitivos.

#### `visit_BlockExpr` ausente no codegen

* `quote:` multi-statement gera `BlockExpr`, que não tinha visitor
  — caía em `generic_visit` retornando `Constant(0)`. Adicionado
  `visit_BlockExpr` executando statements e retornando `final_expr`.

#### `_expand_macro_expr` não passava `macros` ao interpreter

* Macros aninhadas não expandiam: `quadruplo` chamando `dobro`
  falhava com "função não suportada no corpo da macro: 'dobro'".
* Corrigido passando `QuoteInterpreter(macros=self.macros)`.

### 🧪 Testes

Estado após este ciclo:

```text
pytest tests/ -q
510 passed in 141.61s (0:02:21)
```

Testes novos:

* `tests/test_quasiquote_parser.py` — 13 testes:
  * `quote` é keyword reservada.
  * `quote:` multi-linha e single-line.
  * `~x` dentro/fora de quote.
  * `~@xs` dentro de quote; erro fora.
  * `quote:` aninhado.
  * `quote` não pode ser identificador.
  * Bitwise NOT runtime.
  * Formatter preserva a sintaxe.
  * Erro claro quando `quote:` é usado fora de macro.
* `tests/test_quasiquote_expand.py` — 10 testes:
  * Substituição direta continua funcionando.
  * `quote: ~x` (identidade).
  * `unless` canônico.
  * Expressão composta (`~x + 1`).
  * Bloco com `let` (`twice`).
  * Scaffolding no corpo (`choose` com `if`).
  * `quote:` fora de macro → erro.
  * `~x` fora de quote em corpo de macro → bitwise NOT.

### 📚 Documentação

* Nova ADR **`docs/engineering/decisoes/0003-quasiquote.md`**
  documentando design, alternativas descartadas (Lisp backtick,
  S-expr, AST-builder) e fases de implementação.
* Status alterado para "aceito" após Phase 1 e Phase 2.

### 🚧 Não implementado neste ciclo

* **Hygiene automática** — rename de bindings introduzidos por
  `quote:` é manual via `gensym`. Automação fica para v1.
* **`~@` em statement position** — espalhamento de lista de
  statements (fora de `[...]`) fica para v0.9.x.
* **`quote:` em tipo** (`quote_type:`) para gerar `TypeNode` —
  adiado.
* **Pattern matching sobre AST** (`macro_rules!`-style) —
  `~x.kind` para inspeção de nó fica para v1.
* **Migração de `@derive`** para `std/derives.lm` usando quasiquote
  — v0.9.x.
* **Deprecation de `--legacy-slice-copy`** — v0.10.0.

[Unreleased]: https://github.com/adamgabriel701/Lumina/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/adamgabriel701/Lumina/compare/v0.8.0...v0.9.0

---

## [0.8.0] — 2026-09-25

> **Milestone:** slice types (`[T]`) — views tipadas e com comprimento.

Esta versão introduz o tipo `[T]` como view tipada e com comprimento
sobre regiões contíguas de memória, resolvendo a limitação conhecida
de `for x: T in ptr` (loop vazio por falta de comprimento) e
preparando o terreno para APIs de stdlib mais ergonômicas.

### ✨ Adicionado

#### Tipo `[T]` — slice

* Novo tipo primitivo `[T]` representando uma **view** sobre uma
  região contígua de memória: `{T*, i64}`.
* Zero-copy: nenhuma alocação ao criar um slice.
* Integrado com `for`, `len`, `s[i]`, `s.data`, `s.len`.
* `[T]` é um tipo estático, como `int` e `Box<int>`.

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

* Representação LLVM: `%Slice_T_ = { T*, i64 }`, monomorphizada por
  tipo de elemento como `Box<T>`.
* Passado por ponteiro em parâmetros de função (consistente com o
  resto das structs Lumina).

#### `as_slice(p, n)` e `view(arr, a, b)` — builtins

* `as_slice(p: ptr, n: int) -> [int]` — constrói slice a partir de
  ptr + comprimento. O tipo do elemento é `int` por padrão;
  reinterprete via anotação (`let s: [float] = as_slice(p, n)`).
* `view(arr: ptr, a: int, b: int) -> [T]` — constrói slice
  `arr[a..b]`. O tipo do elemento é inferido do `pointee`.
* Ambos são zero-copy — o slice retornado aponta para a memória
  original.

#### `for x in slice:`

* `_visit_for_iterable` reconhece `%Slice_T_*` e extrai `.data` +
  `.len`.
* Resolve a limitação conhecida de v0.7.0: `for x: T in ptr` agora
  funciona quando o comprimento está disponível no slice.

#### Bounds check em `slice[i]` (safe mode)

* Em modo safe-default, `s[i]` verifica `0 <= i < s.len` em runtime.
* Fora dos limites → retorna `0` (para int/float) ou `nil` (para ptr).
* `@unsafe` desliga os bounds checks.

#### `s.data` e `s.len`

* Acesso direto aos campos do slice.
* `s.data: ptr` — ponteiro para o primeiro elemento.
* `s.len: int` — número de elementos.

#### Sub-slicing zero-copy

* `s[a..b]` de slice retorna novo slice view, sem alocação.
* Composição: `v[1..4][1..3]` funciona.

#### Flag `--legacy-slice-copy`

* Restaura o comportamento de `v[a..b]` anterior à v0.8.0
  (cópia em vez de view). Destinada à migração.
* Será removida em v0.10.0.

### 🔧 Alterado

#### `v[a..b]` retorna `[T]` (view) em vez de cópia

* **Breaking change.** Antes, `v[1..3]` copiava para `T*` via
  `malloc`. Agora retorna um slice view `[T]` — zero alocação.
* Strings **mantêm retrocompat**: `s[1..3]` continua retornando
  `str` (cópia via `strncpy`).
* Migração recomendada: substitua `let p: ptr = v[1..3]` por
  `let s: [float] = v[1..3]` e use `s.data` quando precisar do
  ponteiro bruto.

  | Antes | Depois |
  |---|---|
  | `let s = v[1..3]` → `T*` (cópia) | `[T]` (view) |
  | `s[0]` → `T` | `s[0]` → `T` (idêntico) |
  | `print(s)` → imprime ponteiro | `print(s)` → imprime ponteiro |

* Mitigação: `--legacy-slice-copy` restaura o comportamento antigo.

#### Parser: `[T]` reconhecido em posição de tipo

* `parse_type` aceita `[` como prefixo de tipo.
* `fn f(s: [int])` compila.
* Sem ambiguidade: `[` em contexto de tipo (`:` `->` `(` `,`) não
  conflita com array literal.

#### Semantic: `is_assignable` para `[T]`

* `[T] → [U]` — recursão em T/U.
* `[T] → ptr` — coage implicitamente para `.data` (retrocompat).
* `ptr → [T]` — **não** (perde `.len`); use `as_slice(p, n)`.

#### Mangling de slices

* Novo `mangle_slice` em `lumina/common/mangle.py`.
* `'int'` → `'Slice_int_'`; `'[int]'` → `'Slice_int_'` (idempotente);
  `'Box<int>'` → `'Slice_Box_int__'`.

#### Genéricos com slices

* `substitute_generic`, `unify_type`, `expand_type_alias` reconhecem
  `[T]` e recursam no tipo interno.
* `Box<[int]>` funciona em type annotations.

### 🐛 Corrigido

#### `visit_SliceExpr` — `is_string` não computado

* A versão inicial referenciava `is_string` antes de definir,
  disparando `UnboundLocalError` em todo `v[a..b]`. Corrigido
  computando `is_string` imediatamente após `arr_val = visit(node.array)`.

#### `visit_MemberExpr` (semantic) — slices sem campos

* `s.len` e `s.data` falhavam com "Tipo '[int]' não é uma
  Struct/Enum". Adicionado caso explícito para slices com os
  membros `data` e `len`.

#### `_infer_for_elem_type` — slices não reconhecidos

* `for x in v[..]` caía no fallback `int`. Adicionado caso para
  tipo `[T]` → `T`.

#### `visit_AssignStmt` — `s[i] = v` em slice

* Atribuição via index em slice exigia extrair `.data` antes do
  GEP. Sem isso, `s[0] = 42` escrevia no `%Slice_T_*` em vez de no
  buffer de dados.

### 🧪 Testes

Estado após este ciclo:

```text
pytest tests/ -q
487 passed in 126.89s
```

Testes novos:

* `tests/test_slice_basic.py` — 5 casos cobrindo:
  * `len(s)` em slice criado por `v[1..4]`
  * `for x in s` iterando
  * `s[i]` indexando
  * `[int]` como parâmetro de função
  * `s.len` como field access

### 🚧 Não implementado neste ciclo

* **`bytes(s)`** — slice de string (bytes) como `[int]`. Strings
  continuam sendo `str` opaco. Adiado para v0.8.x.
* **`copy(s: [T]) -> ptr`** — migração programática do comportamento
  antigo. Use `--legacy-slice-copy` como workaround.
* **Slice de struct custom** (`[MyStruct]`) — funciona
  estruturalmente (`{%MyStruct*, i64}`), mas não há teste nem doc.
  Cuidado ao usar.
* **Migração de `std/*`** — APIs duais (`sort` + `sort_slice`).
  v0.8.x.
* **Deprecation de `--legacy-slice-copy`** — v0.10.0.

### 📚 Documentação

* Nova seção **Slices** em `docs/guia/linguagem.md`, cobrindo:
  * criação (`v[a..b]`, `as_slice(p, n)`, `view(arr, a, b)`)
  * iteração, indexação, `len`
  * acesso a `.data` e `.len`
  * sub-slicing
  * bounds check em safe mode
  * interoperabilidade com `ptr` e retrocompat com strings
* Nova ADR **`docs/engineering/decisoes/0002-slice-types.md`**
  documentando o design, alternativas descartadas e fases de
  implementação.

[Unreleased]: https://github.com/adamgabriel701/Lumina/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/adamgabriel701/Lumina/compare/v0.7.0...v0.8.0

---

## [0.7.0] — 2026-09-25

> **Milestone:** safe-by-default + preparação para self-hosting.

Esta versão torna a segurança de memória o **comportamento padrão** da
linguagem (`@safe` deixa de ser opt-in) e prepara o terreno para
self-hosting com melhorias na iteração sobre arrays e análise de
escape.

### ✨ Adicionado

#### Safe-by-default global

* Null checks automáticos em `MemberExpr` e `IndexExpr` agora são o
  comportamento **padrão** — `@safe` deixou de ser necessário.
* Novo atributo `@unsafe` desliga os null checks explicitamente:

  ```lumina
  @unsafe
  fn hot_path(u: U) -> int:
      return u.id       # sem null check — mais rápido, mais perigoso
  ```

* Comportamento de migração:
  * Código com `@safe` continua funcionando (o atributo é aceito mas
    ignorado — já é o default).
  * Código sem `@safe` que dependia do SIGSEGV em `u.id` com `u == nil`
    agora retorna `0`. **Breaking change sutil**: para preservar o
    comportamento antigo, use `@unsafe`.
* Closures, cópias especializadas de genéricos (`materialize_generic`)
  e membros de SCCs (mutual TCO) herdam `_safe_mode` do contexto.
  `@unsafe` na função externa propaga para a closure.

#### `for x: T in arr` — iteração tipada sobre `ptr`

* Nova sintaxe opcional de anotação de tipo no cabeçalho do `for`:

  ```lumina
  let precos = [1.5, 2.5, 3.5]
  for x: float in precos:
      print(x)     # imprime float, não bits do f64
  ```

* Funciona também com `for i, x: T in arr:`.
* Motivada pelo caso `fn f(arr: ptr)` chamada com `[1.5, 2.5]`:
  sem a anotação, `arr` é `i64*` e `x` sairia como int truncado.
* O codegen faz `bitcast i64* → f64*` quando o hint diverge do
  `pointee` real (apenas no caminho `ptr`; arrays com tipo próprio
  são intocados).
* Validação em compile-time: hints incompatíveis com o tipo inferido
  do iterável levantam `LuminaError` (via `_is_hint_compatible`).
  Ex: `for x: str in [1, 2, 3]` falha.
* Preservado pelo `lumina fmt`.

#### Escape analysis para `alloc(N)` com N dinâmico (VLA)

* `alloc(N)` com `N` não-literal agora pode virar **VLA**
  (*variable length array*) via `alloca(elem_ty, N)`, contanto que
  todas as condições de segurança valham:

  1. `N` **não** está dentro de loop (`loop_stack` vazio);
  2. a chamada está no **bloco de topo** da função
     (`builder.block == current_body_bb`, ou seja, não em if/else);
  3. a variável **não escapa** (não é retornada, não é passada a
     função externa, não é armazenada em struct);
  4. a variável **não é passada a `free`**.

* Reduz pressão no GC em funções que alocam buffers temporários de
  tamanho dinâmico mas limitado.

* Qualquer dúvida cai para GC/malloc — comportamento anterior
  preservado. Zero regressão em código existente.

#### `lumina/common/attrs.py` — fonte única de atributos

* Módulo referenciado em ~10 arquivos do compilador mas **ausente do
  repositório**. Criado como fonte única de verdade para parsing e
  normalização de `@attr`:

  * `normalize_attrs(attrs)` — normaliza `List[str]`,
    `List[Tuple[str, List]]` e variantes para o formato canônico.
  * `attr_names(attrs)` — apenas os nomes.
  * `has_attr(attrs, name)` — teste de presença.
  * `get_attr_args(attrs, name)` — args do primeiro attr com o nome.

* `codegen/context.py` re-exporta `normalize_attrs` para
  compatibilidade.

### 🔧 Alterado

#### Codegen

* `generate_function_body` — `_safe_mode` agora defaulta para `True`,
  controlado por `@unsafe` em vez de `@safe`.
* `materialize_generic` — mesmo tratamento: cópias especializadas
  herdam o modo safe, `@unsafe` na `gen_def` original desliga.
* `_materialize_scc_dispatcher` — cada membro do SCC resolve
  `_safe_mode` a partir dos próprios attrs (não herda do vizinho).
* `_emit_lambda_closure` — `inherit_safe` agora usa
  `getattr(self, '_safe_mode', True)` em vez de `False`.
* `_try_stack_alloc` — ganhou segundo caminho (VLA) para `N` dinâmico
  seguro. Caminho de `N` literal permanece idêntico.
* `_visit_for_iterable` — aceita `node.elem_type` como hint;
  aplica `bitcast` do `arr_val` apenas no caminho `ptr` genérico.
  Caminhos com `array_lengths` e array literal preservam o
  comportamento anterior, exceto pela aplicação do hint quando
  presente.

#### Parser

* `parse_for` reconhece anotação opcional `: T` entre o nome da
  variável e o `in`. Lookahead de 1 token (`COLON` + `IDENT` vs.
  `COLON` + `NEWLINE`) evita ambiguidade.
* Sintaxes suportadas:

  ```
  for x in arr:
  for i, x in arr:
  for x: float in arr:
  for i, x: float in arr:
  ```

#### Semantic

* `_analyze_for` **infere o tipo do elemento** da variável de loop
  (`_infer_for_elem_type`). Ordem de precedência:

  1. Hint explícito (`for x: T in arr`) — vence; validado contra
     tipo inferido.
  2. Array literal inline (`for x in [1.5, 2.5]`) — tipo do 1º
     elemento.
  3. Variável com `array_elem_types` populado — tipo registrado.
  4. String literal ou variável de tipo `str` — `int` (char i8).
  5. Fallback — `int` (comportamento anterior).

* Antes, `for x in ["a", "b"]` declarava `x: int` (hardcoded),
  quebrando `let y: str = x`.

#### Formatter

* `format_node` para `ForStmt` preserva a anotação `: T` ao
  reemitir o código.

#### AST

* `ForStmt.elem_type: Optional[str] = None` — novo campo. Backwards
  compatible (default `None`).

### 🐛 Corrigido

#### Semantic — inferência de tipo em `for`

* `_analyze_for` declarava **todos** os bindings de loop como `int`
  (hardcoded). `for x in ["a", "b"]: let y: str = x` falhava com
  "Tipo inválido em declaração de 'y'" mesmo com o codegen iterando
  `i8*` corretamente.
* Novo helper `_infer_for_elem_type` infere o tipo pela ordem
  documentada acima.
* Teste de regressão:
  `test_for_hint_type.py::test_without_hint_string_inference_works`.
* Teste negativo:
  `test_for_hint_type.py::test_int_array_with_str_annotation_fails`.

#### Semantic — validação de hint incompatível

* Hint de tipo incompatível com o tipo inferido do iterável falha
  em compile-time em vez de gerar bitcast silencioso.
* Compatibilidade definida por **grupos LLVM**, não por
  `is_assignable`: `int`↔`float` é promoção, mas em `for` seria
  `bitcast` (reinterpretação de bits), que não é o que o usuário
  espera.
* Grupos aceitos: `{int}`, `{float}`, `{bool}`, `{str, fn}`.
  `ptr` é wildcard (hint é fonte de verdade).
* Teste: `test_hint_conflicts_with_array_type_fails`.

#### `lumina/common/attrs.py` ausente

* Múltiplos módulos faziam `from ..common.attrs import normalize_attrs`
  — o import falhava em builds limpos.
* `_extract_args` foi reescrito para aceitar corretamente o formato
  `List[List[str]]` (antes pegava só `item[1]`, descartando o resto).
* Testes: `test_attrs_normalize.py` (13 casos).

#### VLA — segunda condição de segurança

* `_try_stack_alloc` caminho 2 exige que o `builder.block` seja o
  `current_body_bb` (bloco de topo da função). Antes, `alloc(n)`
  dentro de `if` geraria `alloca` condicional — válido em LLVM, mas
  pessimiza e complica razão sobre o IR.
* Coberto por `test_vla_escape.py::test_alloc_in_if_uses_gc`.

### 🧪 Testes

Estado após este ciclo:

```text
pytest tests/ -q
482 passed
```

Testes adicionados neste ciclo:

* `test_safe_default.py` — 9 testes (null check em runtime, `@unsafe`
  remove `safe_nav_*`, herança em closures/generics/SCC).
* `test_for_hint_type.py` — 11 testes (hint `float`/`str`, inferência
  automática, teste negativo, índice, formatter, limitação
  documentada).
* `test_vla_escape.py` — 7 testes (VLA habilitado/desabilitado,
  regressão literal, escape conservador em subscript).
* `test_attrs_normalize.py` — 13 testes (normalização, helpers,
  integração com parser).

### 📚 Documentação

* `docs/guia/linguagem.md`:
  * Seção **`@safe`** reescrita como **Safe-by-default**, com
    `@unsafe` documentado como opt-out.
  * Seção **`for`** atualizada com `for x: T in arr` e a limitação
    sobre `ptr` dinâmico.
  * Seção **Arrays** — nota sobre VLA em `alloc(N)` dinâmico.
* `docs/internals/codegen.md`:
  * Seção **Escape analysis** — segundo caminho (VLA) documentado
    com as 4 condições de segurança.
  * Seção **`@safe`** atualizada para refletir o default invertido.
* `docs/engineering/bugs.md`:
  * Entrada sobre `lumina/common/attrs.py` ausente.
  * Entrada sobre `_analyze_for` hardcoded em `int`.
  * Entrada sobre escape analysis conservadora em subscript.
* `README.md`:
  * Badge de versão atualizado.
  * Seção **Memória e segurança** com nota sobre safe-by-default.

### 🛠️ Tooling

#### LSP — inlay hints funcionais

* `lumina-vscode/lumina_lsp.py`:
  * `validate_and_extract_symbols` agora retorna 9-tuple
    (`+ semantic_tokens`, `+ inlay_hints`), eliminando a
    segunda passada de parse + semantic que existia em
    `_recompute_extras`.
  * `_collect_inlay_hints` lê `decl.var_type` diretamente da AST
    (que o analyzer muta in-place), em vez de chamar
    `analyzer.get_var_info(name)` — fonte única de verdade,
    sem chance de divergir.
  * **Nova code action `refactor.rewrite`**: "Anotar tipo inferido:
    `x: int`". O usuário posiciona o cursor sobre uma variável
    cujo tipo foi inferido e o VS Code oferece materializar
    a anotação (`let x = 10` → `let x: int = 10`).

#### Lexer self-hosted (`lumina_core/lexer.lm`)

* **Deixou de ser esqueleto**: paridade funcional com o lexer
  Python (`lumina/lexer/lexer.py`).
* Adicionado:
  * `INDENT` / `DEDENT` via `indent_stack` (antes: TODO).
  * `paren_depth` para supressão de `NEWLINE` dentro de
    `(...)`, `[...]`, `{...}`.
  * Suporte a `\r\n` (CRLF).
  * `0b` / `0o` — paridade com o lexer Python pós-v0.6.0.
  * `DEDENT` final + `EOF` corretos.
* Estrutura `Lexer` com campos `source`, `pos`, `length`,
  `line`, `col`, `paren_depth`, `at_line_start`,
  `indent_stack`, `indent_size`.
* Este arquivo agora serve como base para o **parser
  self-hosted** (Sprint 12 da ADR de self-hosting).

[Unreleased]: https://github.com/adamgabriel701/Lumina/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/adamgabriel701/Lumina/compare/v0.6.0...v0.7.0

---

## [0.6.0] — 2026-09-25

> Desenvolvimento posterior ao milestone `v0.5.0-linker`.

### ✨ Adicionado

#### Otimizador O1 integrado
* Integração do otimizador **O1** diretamente no pipeline de compilação.
* Otimização aplicada de forma integrada ao fluxo de geração de código.
* Preservação do comportamento semântico dos programas durante a otimização.

#### Pattern Matching de Structs
* Suporte a **desestruturação de structs** em padrões.
* Pattern matching de campos de structs.
* Integração dos padrões de structs ao sistema existente de `match`.
* Novos testes cobrindo os casos de pattern matching adicionados.

#### Sugestões automáticas
* Sistema de sugestões automáticas para identificadores desconhecidos.
* Implementação baseada em **distância de Levenshtein**.
* Mensagens de erro mais úteis para nomes digitados incorretamente.
* Sugestões integradas ao diagnóstico semântico.

#### Tipos de função
* Suporte a tipos de função no formato:

```text
fn(T1, T2) -> R
```

* Integração dos tipos de função ao sistema de tipos.
* Suporte a múltiplos parâmetros.
* Suporte a tipo de retorno explícito.
* Integração com closures e callbacks.

#### Closures como callbacks
* Closures podem ser utilizadas como callbacks.
* Unificação da representação de funções e closures por meio de ponteiros `fn`.
* Suporte a funções de primeira classe em APIs que recebem callbacks.

#### Escape sequences
* Suporte a sequências de escape em strings.
* Integração das novas sequências com lexer, parser e codegen.

#### Macros com múltiplas instruções
* Macros podem conter múltiplas instruções.
* Melhor integração das macros com o parser e o restante do pipeline.

#### Tail Call Optimization
* Suporte a **TCO (Tail Call Optimization)** para chamadas recursivas diretas.
* Redução do crescimento da stack em casos de recursão em posição de cauda.

#### LSP
* Novos **inlay hints**.
* Novas **code actions**.
* Melhor integração dos recursos de análise do compilador com o Language Server.

#### Cross-compilation
* Suporte ao parâmetro:

```text
--target=<triple>
```

* Testes de cross-compilation para arquiteturas adicionais.
* Validação de execução de binários cross-compilados utilizando QEMU.

#### CLI
* Propagação correta dos códigos de saída dos programas executados.
* Melhor integração das novas opções do compilador com o pipeline de build.

#### Linker próprio — W^X estrito
* O linker `lumina-ld` agora emite **dois segmentos `PT_LOAD`** em vez de um único segmento RWX:
  * **RX** — cabeçalhos ELF, `.text`, `.rodata`
  * **RW** — `.data`, `.bss`, heap folga
* Page-align entre `.rodata` e `.data` garante que nenhuma página é simultaneamente executável e gravável.
* Compatível com kernels hardened modernos (`CONFIG_STRICT_KERNEL_RWX`).
* Modo legado (segmento único RWX) disponível com `-DLEGACY_RWX` — **não recomendado**.

#### Preferência de símbolo do usuário em colisões
* Símbolos `main` vindos de objetos de runtime (`start.o` / `rt.o`) são **filtrados em `build_gsyms`**.
* Comportamento determinístico, independente da ordem dos inputs na linha de comando.
* Resolve colisões residuais sem exigir que o usuário saiba da ordem correta de link.

#### Alloca hoisting real
* Novo helper `_fn_emit_alloca` em `codegen.py` insere `alloca` no **fim do entry block** (antes do terminador), via `position_before(terminator)`.
* Aplicado em `codegen_fstring` (`literals.py`), `num_to_str` (`operators.py`) e `str_buf` (`builtins.py`).
* Elimina crescimento de stack em loops que usam buffers temporários.
* Detecção de terminador via `opname` (compatível com llvmlite >= 0.42).

#### Init runtime de globais `mut X = <não-literal>`
* `_emit_mutable_global` agora aceita inicializadores não-constantes: `alloc(N)`, `alloc_bytes(N)`, chamada a função do usuário, ou anotação explícita de tipo.
* Zero-init no `LLVMGlobalVariable` + init runtime emitida no início de `main_body` (via `_deferred_globals`).
* Cobre `chip8`, `coroutines` e qualquer programa com buffers globais.
* `let X = ...` no topo continua inline-constante (não vira global).
* Dedup por nome — `mut X` em dois arquivos importados não dispara `DuplicatedNameError`.

#### Constantes de codegen centralizadas
* Novo módulo `lumina/codegen/constants.py` — fonte única para magic numbers do codegen.
* `I64_BYTES`, `MIN_ENUM_SIZE`, `CLOSURE_BLOCK_SIZE`, `STACK_ALLOC_LIMIT`.

#### Resolução de imports consolidada
* Novo módulo `lumina_cli/compiler/paths.py::resolve_import_path`.
* Antes duplicada em `parse.py` e `utils.py::get_all_dependency_files`.
* Uma única fonte de verdade para `std/X`, `./X`, `lumina_modules/X`.

#### Cache de variantes de enum
* `_find_enum_variant` agora constrói um cache `variant_name → (enum_base, idx)` na primeira chamada.
* Corrige bug latente onde enum genérico podia ser retornado com nome monomorphizado (`Custom<int>` em vez de `Custom`).

#### Playground — bind em loopback
* O servidor HTTP do `lumina playground` escuta em `127.0.0.1` por padrão, em vez de `0.0.0.0`.
* Flag opcional `host` na API `run_server` para expor intencionalmente.
* Mitiga vetor crítico: qualquer máquina na rede podia executar JIT arbitrário via port-forward público.

#### Infra de diagnóstico
* Novo `linker/test_skipped.sh` — classifica cada exemplo skipado em todos os estágios (compile, asm, link, run).
* Novo `linker/investigate_segfaults.sh` — gdb backtrace automático de segfaults.
* Novo `linker/skip.txt` — skip list externalizada (antes hardcoded em `triagem.sh`).

#### Arrays tipados (elemento preserva tipo)

* `visit_ArrayExpr` agora infere o tipo do elemento pelo primeiro elemento:
  * `[1, 2, 3]`          → `[i64;3]`
  * `[1.5, 2.5, 3.5]`    → `[f64;3]` — `v[0]` retorna `float`, não bits do `f64`
  * `["a", "b"]`         → `[i8*;2]` — `v[0]` retorna `str`, não ponteiro formatado como `int`
* `for x in [1.5, 2.5]` itera `f64`.
* `mut v = ["a", "b"]; v[1] = "c"` valida tipo do elemento em compile-time.
* `let s = v[1..]` de `[f64;N]` copia para `f64*`, preservando precisão.
* Novo mapa `SemanticAnalyzer.array_elem_types` rastreia o tipo do elemento
  de variáveis de array literal e é consultado por `visit_IndexExpr`.
* `_try_stack_alloc` popula `array_lengths[name]`, permitindo `arr[a..]`
  para arrays stack-allocated.

#### Infraestrutura de atributos

* Novo módulo `lumina/common/attrs.py` — fonte única de verdade para
  parsing e normalização de `@attr` em todo o compilador.
* API: `normalize_attrs`, `attr_names`, `has_attr`, `get_attr_args`.
* `codegen/context.py` re-exporta `normalize_attrs` para compatibilidade.

#### Coerção bit-exact de payloads de enum

* Novo helper `_coerce_enum_payload_store` em `expressions/methods.py`:
  * `float ↔ i64` via `bitcast` (não `fptosi`, que truncaria)
  * `str ↔ i64` via `ptrtoint`/`inttoptr`
  * `int ↔ int` via `sext`/`zext`/`trunc`
* Novo helper `_coerce_enum_payload_load` em `statements/match.py` faz
  a conversão inversa ao fazer binding de payloads.
* `_find_enum_variant` ganhou `_invalidate_variant_cache` para quando
  `struct_defs` é modificado por monomorphização.

#### Literais binários e octais

* Lexer agora aceita:
  * `0b...` / `0B...` — binário (`let x = 0b1100` → 12)
  * `0o...` / `0O...` — octal (`let x = 0o17` → 15)
* O loop de dígitos é restrito ao alfabeto válido do prefixo
  (`0b` aceita só `01`, `0o` aceita `0-7`, `0x` aceita `0-9a-f`),
  evitando consumir identificadores adjacentes.
* Antes, `0b1100` era lido como `NUMBER(0)` seguido de `IDENT(b1100)`.

#### `CompoundAssignStmt` — `x op= y` com avaliação única

* Novo nó de AST para operadores compostos (`+=`, `-=`, `*=`, `/=`,
  `&=`, `|=`, `^=`).
* Antes, o parser desaçucarava para `AssignStmt(target, BinaryExpr(op,
  target, value))`, avaliando o lvalue **duas vezes**. Para
  `arr[f()] += v`, isso chamava `f()` duas vezes.
* O codegen agora resolve o endereço do alvo uma vez (`_resolve_lvalue`),
  carrega, aplica o operador e escreve de volta.

#### Cases com corpo vazio (fallthrough)

* `match` agora aceita cases vazios que mesclam patterns:

  ```lumina
  match n:
      case 1:
      case 2:
          print("um ou dois")
  ```

* O parser detecta corpo vazio e mescla o pattern do case seguinte até
  encontrar um case com corpo. Guards e bindings são rejeitados (um
  binding sem corpo não tem semântica).

#### `ForStmt.index_var` — separação do índice

* Novo campo `index_var` em `ForStmt`. Antes, o parser codificava
  `for i, x in arr:` como `var_name = "i,x"` — string com vírgula,
  frágil e impossível de validar em compile-time.
* Agora:
  * `for i, x in arr` → `var_name = "x"`, `index_var = "i"`
  * `for x in arr`    → `var_name = "x"`, `index_var = None`
* Compatível com o código existente (default `None`).

### 🔧 Alterado

#### Pipeline de compilação
* Refatoração de componentes internos do parser.
* Refatoração da análise semântica.
* Refatoração do codegen em componentes mais especializados.
* Melhor separação de responsabilidades entre as etapas do compilador.
* Integração mais consistente entre otimização, codegen e linking.

#### Sistema de tipos
* Expansão da cobertura de tipos.
* Melhor validação de tipos.
* Melhor integração entre tipos de função, closures e callbacks.
* Ampliação dos testes end-to-end relacionados ao sistema de tipos.

#### `match`
* Melhorias no parser e na análise semântica de expressões `match`.
* Expansão para padrões envolvendo structs.
* Cases com corpo vazio agora mesclam patterns (fallthrough).

#### Codegen
* Correções em diferentes caminhos de geração de código LLVM.
* Melhor tratamento de funções que terminam após determinadas operações de retorno.
* Correções relacionadas ao gerenciamento de stack em determinados padrões de código.
* Melhor integração com o runtime freestanding.

#### Runtime
* Expansão e correção de componentes do runtime.
* Melhor integração entre o runtime e o linker próprio.
* Documentação interna sobre o alocador linear em `rt.c`: `free()` é no-op por design; churn de alocação vaza memória sob `--linker=self`.

#### Representação de arrays unificada

* `visit_ArrayExpr` muda o contrato público: retorna `T*` (ponteiro para
  1º elemento) em vez de `[T;N]*` (ponteiro para array). Unifica a
  representação com `alloc(N)` e elimina a necessidade de GEP duplo na
  indexação.
* Consumidores internos ajustados: `visit_IndexExpr`, `_load_index`,
  `_visit_for_iterable`, `visit_SliceExpr`, `visit_VarDecl`.

#### Normalização de attrs

* `Function.attrs` passa a ser `List[Tuple[str, List]]` (era `List[str]`),
  igual a `StructDecl.attrs`. O parser para de projetar.
* `SemanticAnalyzer.analyze`, `DerivesMixin._expand_derives` e
  `RegistrationMixin._apply_llvm_attrs` passam a usar `normalize_attrs`.

#### Slice bounds usam `_to_i64_int`

* Novo helper `_to_i64_int` em `members.py` centraliza a conversão
  `iN → i64`, usando `zext` para `i1` (bool) e `sext` para outros
  inteiros. Antes, `sext` era usado em `i1`, transformando
  `n == 4` (i1 = 1) em `i64 -1`.

### 🐛 Corrigido

#### `chip8`
* Corrigido um caminho de geração de código no qual `main` poderia terminar sem uma instrução `ret` adequada após determinadas operações.
* O problema tornou-se observável durante a utilização do linker próprio e do runtime freestanding.
* **Reescrita de `draw_screen`**: passa a reusar um buffer de 65 bytes por linha em vez de concatenar strings (2048 alocações por chamada → 32). Elimina SIGSEGV no `--linker=self` por esgotamento do heap.
* **Máscara `0xFF` em opcodes**: `memory[pc]` retorna `i8` sign-extended; sem máscara, `0xE0` vira `-32` e quebra o dispatch. Fix só no `.lm`.

#### `coroutines`
* Corrigido problema em que `main_ctx` e `scheduler_ctx` (globais com `alloc_bytes`) eram re-avaliados a cada referência. Agora inicializados uma vez via `_deferred_globals`.

#### `gc_test`
* Corrigido problema relacionado à utilização de `alloca` dentro de loops.
* A implementação anterior podia provocar crescimento contínuo da stack (RSP até ~2 GB em 100k iterações).
* Novo helper `_fn_emit_alloca` resolve o sintoma em todos os sítios que alocavam buffer temporário em loop.

#### Codegen
* Correções em casos específicos de geração de código.
* Melhor tratamento de retornos em funções.
* Correções expostas pelos testes end-to-end utilizando o linker próprio.

#### Linker
* Correções no tratamento de símbolos `SHN_COMMON`.
* Adição/tratamento de símbolos sintéticos necessários durante o linking.
* Correções no layout dos segmentos `PT_LOAD`.
* Correções relacionadas à integração com o runtime freestanding.
* **`main` sintético em `rt.o`**: um `int main` residual no runtime colidia com o `main` do usuário, fazendo todo link com `--linker=self` abortar com "multiple definition of 'main'".
* **Filtro defensivo em `build_gsyms`**: símbolos `main` vindos de runtime são descartados preventivamente — não dependem mais da ordem dos inputs.

#### Otimizador O1
* `_optimize_ir` usava `llvm.create_pass_manager_builder()`, removido do llvmlite >= 0.42.
* Nova implementação detecta em runtime qual API está disponível:
  * `create_new_module_pass_manager()` (0.42+)
  * `create_pass_manager_builder()` (legado)
  * `PassManagerBuilder` (legado alternativo)
* Fallback: passes individuais do New Pass Manager.
* Sem warning ruidoso quando nenhuma API compatível está disponível.

#### TCO — `var_types` como set
* `_materialize_scc_dispatcher` inicializava `var_types` como set (`{p.type_ann}`) em vez de dict (`{p.name: p.type_ann}`).
* Bug latente: crashava com `AttributeError: 'set' object has no attribute 'get'` quando um membro do SCC chamava função genérica.
* Novo teste de regressão em `test_tco_mutual.py::test_scc_member_calls_generic`.

#### `_fn_emit_alloca` — detecção de terminador
* Primeira versão usava `is_terminator` como propriedade; llvmlite não expõe essa API.
* Corrigido para detectar terminador via `opname` (`br`, `ret`, `unreachable`, `switch`, ...).

#### Exemplos
* Correções necessárias para que os exemplos possam ser compilados e executados pelos diferentes pipelines disponíveis.
* Melhorias na triagem automática dos exemplos.
* `bootstrap_lexer`, `database`, `json_parser` resgatados da skip list do linker.

#### Semantic — inferência e type checking

* `visit_UnaryExpr` retornava `None`, quebrando a inferência de
  `let x = -5` (`x` ficava sem tipo e o codegen assumia `int` por default)
  e `let y = not b`. Agora retorna `int`/`float`/`bool` conforme o operador.
* `_infer_var_decl_type` não cobria `UnaryExpr`; `let x = -5.5` inferia
  `int` e truncava o valor. Adicionado branch explícito.
* `_resolve_kwargs` descartava `kwargs` silenciosamente quando a função
  era desconhecida (builtin, método de std). Agora levanta `LuminaError`
  com mensagem acionável — `print(x: 1)` falha em vez de compilar errado.
* `_expand_type_aliases` era uma travessia ad-hoc que não cobria
  `LambdaExpr`, `CastExpr` nem `MacroCallStmt`. Reescrita como travessia
  genérica sobre dataclasses da AST. `type MyInt = int` dentro de
  `fn(x: MyInt)` ou `y as MyInt` agora funciona.
* `_analyze_match_stmt` tipava todos os bindings como `int` (hardcoded),
  quebrando `case Has(s): s + "!"` quando o payload era `str`. Agora
  consulta `enum_def.variants` e substitui type params de enums genéricos
  via `substitute_generic`.
* Struct patterns (`case Ponto { x, y }`) declaravam `x` e `y` com o
  tipo da struct inteira em vez do tipo do campo correspondente —
  `x + y` falhava com "Operador '+' não definido para 'Ponto'".
* `expand_type_alias` retornava silenciosamente em `_depth > 32`. Agora
  levanta `LuminaError` com hint sobre ciclos (`type A = B; type B = A`).
* `_analyze_assign` não validava tipo em `arr[i] = v` para arrays de
  `ptr`. Agora infere do `array_elem_types` quando disponível.

#### Semantic — normalização de attrs

* `Function.attrs` era `List[str]` e `StructDecl.attrs` era
  `List[Tuple[str, List]]`. Cada consumidor tinha que adivinhar o
  formato (`if 'macro' in attrs` quebrava silenciosamente). Unificado
  em `List[Tuple[str, List]]` via novo `lumina/common/attrs.py`.
* `@derive` em enum era silenciosamente ignorado. Agora é erro
  explícito com mensagem acionável.
* `and`/`or` rejeitava operandos `int` no semantic, mas o codegen
  aceitava. Unificado: `int` é tratado como bool (0 = false).
* Guard de duplicata em `_resolve_trait_defaults` ganhou mensagem
  distinguindo trait-default de impl explícito, com hint para o caso
  em que ambos estão presentes.

#### Codegen — arrays tipados

* `visit_ArrayExpr` retornava `[T;N]*` (ponteiro para array), exigindo
  GEP duplo na indexação. Agora retorna `T*` (ponteiro para 1º
  elemento), unificando a representação com `alloc(N)`.
* `_load_index` forçava todo valor lido para `i64` via
  `_normalize_loaded`, corrompendo `[1.5, 2.5][0]` (retornava bits do
  `f64`) e `["a","b"][0]` (retornava ponteiro formatado como `int`).
* `_visit_for_iterable` hardcodava `i64` como element type — `for x in
  [1.5, 2.5]` iterava bits em vez de floats.
* `visit_VarDecl` bitcastava `T*` para `i64*` no slot, apagando o tipo
  do elemento. Corrigido com ordem explícita de branches: `alloc` e
  `alloc_bytes` primeiro (tipos fixos), depois structs, depois arrays
  literais, depois fallback.
* `visit_SliceExpr` copiava para buffer `i64*` fixo, mesmo para
  `[f64;N]` e `[i8*;N]`. Agora o buffer segue o tipo do elemento do
  source.

#### Codegen — enums com payload `str`/`float`

* `_construct_enum` usava `_coerce_for_store`, que faz `fptosi` para
  `float` — perdendo precisão. `Val(3.5)` virava `Val(3.0)`.
* `_emit_bindings` carregava o payload como `i64` cru sem converter
  para o tipo declarado. `case Has(s): s + "!"` formatava o ponteiro
  como número (ex: `105542705766414!`).
* Novo helper `_coerce_enum_payload_store` faz `bitcast` (não
  `fptosi`) entre `f64` e `i64`, `ptrtoint`/`inttoptr` entre ponteiro
  e `i64`, preservando bits exatos.
* Bug adicional: para enums genéricos (`Box<T>`), `declared = "T"` era
  type param não-resolvido — `get_llvm_type("T")` retornava `i64`, mas
  o slot de `Box_str_` era `i8*`. `store i8* to i64*` quebrava. Fix:
  type param não-resolvido → usar o slot type diretamente.

#### Codegen — builtins

* `argv(i)` fazia `load` cego de `__lumina_argv[i]`. Sem argumentos,
  `argv(1)` retornava `NULL` e `len(argv(1))` fazia `strlen(NULL)` →
  SIGSEGV. Isso afetava **todos os benchmarks parametrizados por argv**
  (`fib.lm`, `primes.lm`, etc.) quando rodados sem argumentos. Agora
  faz bounds-check em runtime e retorna `""` quando `argv == NULL`,
  `idx < 0` ou `idx >= argc`.

#### Codegen — infraestrutura

* `_llvm_ty_to_str` retornava `"unknown"` para `VoidType`, `IntType(32)`,
  `ArrayType`, `LiteralStructType` e `IdentifiedStructType`. Adicionados.
* `_make_fn_wrapper` crashava em runtime para funções variádicas.
  Agora levanta `LuminaError` com mensagem clara.
* `codegen_method_call` usava `raise Exception("...")` genérico em vez
  de `LuminaError` — sem linha/coluna, sem cor no terminal. Corrigido.
* `self.functions_table[real_method_name]` fazia `KeyError` cru em
  cache inconsistente. Agora usa `.get` com erro explícito.
* Removido cache `_fn_closure_blocks` que gerava IR inválido
  (dominance violation) quando a mesma função nomeada era usada como
  valor em blocos irmãos. Ex: `std/sort.lm` usa `_cmp_asc` em dois
  branches — o `%_cmp_asc_closure` era definido em A e reusado em B,
  e o LLVM rejeitava o IR.

#### Codegen — `visit_NumberExpr`

* Refatoração para suportar `0b`/`0o` introduziu regressão silenciosa:
  `int("3.14")` levanta `ValueError` em Python, e o `except` devolvia
  `0.0`. Todo float virava zero. Corrigido com checagem explícita de
  `is_float` antes do parsing, e base explícita por prefixo.

#### Codegen — slice bounds com `i1`

* `visit_SliceExpr` usava `sext` para converter bounds para `i64`.
  Para `n == 4` (i1 = 1), `sext i1 1 → i64` produz `-1` (todos os
  bits 1). Isso transformava `length = 1` em `length = -1`, levando
  a `malloc(-8)` → NULL → SIGSEGV em `s[0]`. Novo helper
  `_to_i64_int` usa `zext` para `i1`.

#### Codegen — dead code

* Segundo bloco `if node.op in ('and', 'or')` em
  `lumina/codegen/expressions/operators.py::visit_BinaryExpr` era
  inalcançável — o primeiro bloco já faz short-circuit e retorna via
  `phi`. Removido com comentário explicativo.

#### Parser — blocos de comentário `/* */` em qualquer coluna

* `_handle_indent` só ignorava `#` no início de linha. `/* */` em
  coluna diferente do código ao redor disparava INDENT/DEDENT espúrio,
  quebrando o parse:

  ```lumina
  fn main() -> int:
      let x = 10
  /* bloco em col 0 */
      let y = 20
  ```

  Agora `/*` é tratado do mesmo jeito que `#`.

#### Parser — `trait` e `impl` sem corpo

* `trait Marker:` sem corpo (marker trait) falhava com "Esperado
  INDENT". `impl Trait for S:` sem corpo (só métodos default) idem.
  Agora ambos aceitam corpo vazio, consumindo newlines/comentários
  antes de decidir se há bloco.

#### Parser — slice bound com comparação

* `arr[a..b == c]` falhava em `expect(RBRACKET)` porque bounds usavam
  `parse_additive` diretamente. Novo `_parse_slice_bound` cobre
  additive e comparações binárias, cobrindo o caso raro mas real de
  bounds computados.

### 🧪 Testes

A suíte de testes foi ampliada continuamente durante o desenvolvimento.

Estado informado pelo projeto:

```text
pytest tests/ -q
523 passed
```

Verificações adicionais:

```text
python3 run_tests.py
28/28 verifications OK
```

Execução dos exemplos:

```text
./scripts/check_examples.sh --run
55 PASS / 16 SKIP / 0 FAIL
```

Triagem do linker próprio:

```text
./linker/triagem.sh examples
PASS=59 FAIL-COMPILE=0 FAIL-LINK=0 FAIL-RUN=0 SKIP=12
```

**Paridade completa**: o modo `--linker=self` produz o mesmo resultado que o clang
nos exemplos (PASS/SKIP/FAIL idênticos).

Os números de exemplos ignorados diferem entre os scripts porque as duas verificações
possuem escopos diferentes.

#### Testes adicionados neste ciclo

* `test_gc.py::test_default_build_uses_gc_malloc` — **deduplicado** (aparecia 2x).
* `test_tco_mutual.py::test_scc_member_calls_generic` — regressão do bug `var_types`.
* `test_semantic_hardening.py` — 11 testes (enum str payload, unary inference,
  type alias em lambda/cast, kwargs em builtin, `and`/`or` com int,
  arr assign type check).
* `test_match_payload_str.py` — 3 testes (str/int/float payloads).
* `test_codegen_hardening.py` — 5 testes (`_llvm_ty_to_str`, varargs, arrays).
* `test_codegen_quickwins.py` — 9 testes (`argv` bounds-check, array slice).
* `test_typed_arrays.py` — 15 testes (arrays de `f64` e `str`).
* `test_fn_in_branches.py` — 3 testes (regressão do cache `_fn_closure_blocks`).
* `test_parser_lexer_edge_cases.py` — 11 testes (block comment em coluna
  diferente, trait/impl sem corpo).
* `test_parser_fixes_10b.py` — 16 testes (`CompoundAssignStmt`,
  empty case fallthrough, slice bound com comparação, `ForStmt.index_var`).
* `test_binary_literals.py` — 7 testes (`0b`, `0o`, `0x`, compound assign
  bitwise, shift).

### 🗑️ Removido

* Dead code: segundo bloco `if node.op in ('and', 'or')` em
  `lumina/codegen/expressions/operators.py::visit_BinaryExpr`.
* Cache `_fn_closure_blocks` em `lumina/codegen/helpers.py`
  (introduzia bug de dominância sem ganho relevante).
* `lumina_bundle.txt` (bundle antigo, vazio, mantido por engano).
* Arquivo `output.ll` de build anterior.

### 📚 Documentação

* Documentação do linker próprio adicionada em:

```text
docs/internals/linking.md
```

* Documentada a arquitetura interna do `lumina-ld`.
* Documentadas as fases do processo de linking.
* Documentado o processo de resolução de símbolos.
* Documentado o layout do executável.
* Documentado o processo de relocação.
* Documentada a geração do ELF final.
* Documentados símbolos sintéticos.
* Documentada a integração do linker com a CLI.
* Documentado o runtime freestanding.
* Documentados pontos de extensão e debugging do linker.
* Nova seção **Arrays** em `docs/guia/linguagem.md`, cobrindo:
  * array literal com inferência de tipo do elemento
  * alocação dinâmica (`alloc` / `alloc_bytes`)
  * indexação, atribuição, iteração, slicing
  * limitações conhecidas (arrays passados como `ptr` perdem o tipo)
* Nova seção **Literais numéricos** em `docs/guia/linguagem.md`
  cobrindo `0b`, `0o`, `0x`, decimais e floats.
* Nova seção **Operadores `op=`** documentando avaliação única do lvalue.
* Nova seção **Cases com corpo vazio** em `docs/guia/linguagem.md`.
* `@derive` em enum agora documentado como erro explícito.
* README atualizado com:
  * status do compilador;
  * linker próprio;
  * runtime freestanding;
  * arrays tipados;
  * literais binários/octais;
  * operadores compostos;
  * testes;
  * exemplos;
  * benchmarks;
  * limitações;
  * arquitetura do projeto.

[Unreleased]: https://github.com/adamgabriel701/Lumina/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/adamgabriel701/Lumina/compare/v0.5.0-linker...v0.6.0

---

## [0.5.0-linker] — 2026-09-23

> **Milestone:** linker próprio + runtime freestanding.

Esta versão representa a introdução do pipeline de linking próprio do Lumina para executáveis ELF x86_64 Linux.

### ✨ Adicionado

#### Linker próprio — `lumina-ld`

* Novo linker estático próprio implementado em C.
* Suporte inicial a:

```text
ET_REL → ET_EXEC
```

* Pipeline dividido em cinco fases principais:

  1. parsing;
  2. resolução de símbolos;
  3. layout;
  4. relocação;
  5. escrita do ELF final.

* Suporte inicial à arquitetura:

```text
x86_64
```

* Geração de executáveis ELF.
* Integração do linker ao pipeline do compilador.

#### Relocações

Suporte às seguintes relocações x86_64:

```text
R_X86_64_64
R_X86_64_PC32
R_X86_64_PLT32
R_X86_64_32
R_X86_64_32S
R_X86_64_PC64
```

* Suporte a relaxações relacionadas a:

```text
GOTPCREL
GOTPCRELX
REX_GOTPCRELX
```

#### Runtime freestanding

* Novo runtime sem dependência de libc para o pipeline do linker próprio.
* Implementação de `_start` em assembly x86_64.
* Utilização direta de syscalls Linux.
* Suporte a operações básicas de memória.
* Operações de strings.
* Console e file descriptors.
* I/O de arquivos.
* Operações matemáticas.
* Geração de números aleatórios.
* `sleep`.
* Sockets.
* `epoll`.
* Suporte relacionado a coroutines.
* Suporte relacionado a threads.
* Shims necessários para o garbage collector.

Arquivos principais:

```text
start.S
rt.c
```

#### CLI

* Novo modo:

```text
--linker=self
```

* Permite selecionar o linker próprio do Lumina.
* O pipeline compila os objetos utilizando LLVM/Clang e realiza o linking final com:

```text
linker/lumina-ld
```

* O cache de compilação passa a considerar o tipo de linker utilizado.
* O modo com linker próprio utiliza `--no-gc` implicitamente quando necessário ao pipeline.

#### Testes de integração

* Adicionado suporte à execução dos exemplos utilizando o linker próprio.
* Criada triagem específica para distinguir:

  * falhas de compilação;
  * falhas de linking;
  * falhas de execução;
  * exemplos ignorados.

---

### 🔧 Alterado

#### Linking

* O projeto passa a possuir duas estratégias de linking:

  * pipeline convencional baseado em Clang;
  * linker próprio do Lumina.

* O linker próprio é direcionado ao ambiente:

```text
Linux x86_64
```

* Recursos de cross-compilation e WASM continuam utilizando as ferramentas LLVM/Clang apropriadas.

#### Runtime

* Separação mais clara entre funcionalidades dependentes de libc e o runtime freestanding.
* Adaptação de funcionalidades para execução através de syscalls Linux.

---

### 🐛 Corrigido

#### Runtime

* Corrigidos componentes necessários para execução de programas sem libc.
* Adicionados símbolos e funções necessárias para aplicações reais do projeto.

#### Codegen

* Corrigido o problema de stack overflow observado em `gc_test`.
* Corrigido o caminho de geração de código que poderia deixar `chip8` sem retorno adequado.

---

### 🧪 Testes

Estado documentado no desenvolvimento deste milestone:

```text
54 PASS
17 SKIP
0 FAIL
```

O pipeline convencional e o pipeline utilizando o linker próprio foram comparados durante a validação.

---

## Histórico anterior

> As versões abaixo representam funcionalidades e marcos anteriores do projeto conforme documentados durante o desenvolvimento. Detalhes adicionais devem ser mantidos apenas quando correspondentes aos respectivos tags/releases existentes no repositório.

### Desenvolvimento anterior — Setembro de 2026

#### Sistema de funções

* Adicionados tipos de função:

```text
fn(T1, T2) -> R
```

* Suporte a funções como valores.
* Suporte a callbacks.
* Integração com closures.

#### Closures

* Closures passaram a poder ser utilizadas como callbacks.
* Representação unificada por meio de ponteiros `fn`.

#### Parser e semântica

* Refatoração do parser em componentes especializados.
* Refatoração da análise semântica.
* Refatoração do codegen.
* Melhor organização interna do compilador.

#### Pattern matching

* Expansão do sistema de `match`.
* Melhorias na análise semântica.
* Maior cobertura de testes.

#### Operadores

* Expansão do suporte a operadores bitwise.
* Correções no parser e codegen associados.

#### TCO

* Implementação de tail-call optimization para recursão direta em posição de cauda.

#### LSP

* Suporte a inlay hints.
* Suporte a code actions.
* Melhor integração entre diagnósticos do compilador e editor.

#### Cross-compilation

* Introdução do parâmetro:

```text
--target=<triple>
```

* Validação de targets alternativos.
* Testes com QEMU para execução de binários destinados a arquiteturas diferentes.

#### CLI

* Melhor tratamento de códigos de saída.
* Correções no comportamento de comandos de execução.

#### Testes

* Expansão progressiva da suíte de testes.
* Testes de integração end-to-end.
* Testes de tipos.
* Testes de parser.
* Testes de codegen.
* Testes de exemplos completos.

---

## Convenções

As mudanças são agrupadas nas seguintes categorias:

* **✨ Adicionado** — novas funcionalidades.
* **🔧 Alterado** — mudanças em funcionalidades existentes.
* **🐛 Corrigido** — correções de bugs.
* **🧪 Testes** — mudanças na infraestrutura ou cobertura de testes.
* **📚 Documentação** — mudanças exclusivamente documentais.
* **⚡ Performance** — melhorias de desempenho.
* **🗑️ Removido** — funcionalidades removidas.
* **🔒 Segurança** — correções relacionadas à segurança.

---

## Links

* [Repositório](https://github.com/adamgabriel701/Lumina)
* [Milestone `v0.5.0-linker`](https://github.com/adamgabriel701/Lumina/releases/tag/v0.5.0-linker)

[Unreleased]: https://github.com/adamgabriel701/Lumina/compare/v0.5.0-linker...HEAD
[0.5.0-linker]: https://github.com/adamgabriel701/Lumina/releases/tag/v0.5.0-linker