# Linker próprio (`lumina-ld`)

Linker estático ELF x86_64 minimalista, escrito em C, que substitui o
`clang`/`ld` na etapa de linkagem nativa quando `lumina build --linker=self`
é passado.

## Por quê

O pipeline padrão do Lumina gera LLVM IR e entrega para o `clang`, que faz
codegen e linkagem em uma única invocação. Funciona, mas deixa uma
dependência opaca: o usuário precisa ter `clang` + `ld` + `glibc` + `libgc`
instalados, e não há visibilidade sobre o que acontece entre o `.ll` e o
binário final.

O `lumina-ld` substitui a etapa `.o → executável` por um linker próprio. O
resultado é:

- **Sem dependência de libc, libgc, ld, ou crt0 do sistema** — o binário é
  totalmente estático (`file` reporta `statically linked`).
- **Sem dynamic linker** — não há `/lib64/ld-linux-x86-64.so.2` no caminho.
- **Menor** — o executável gerado é tipicamente 15–25% menor que o
  equivalente via clang, porque não carrega tabela de relocação dinâmica,
  PLT, GOT, nem `.eh_frame` completo.

Não é uma reimplementação do GNU ld. É o subconjunto mínimo que o Lumina
realmente precisa.

## Como funciona

O linker implementa as 5 fases clássicas descritas em *Linkers & Loaders*
(Levine). Cada fase vive em uma função própria em `linker/link.c`:

### Fase 1 — Parsing (`load_input`)

Lê cada `.o` via `mmap`, valida o cabeçalho ELF (`ET_REL`, x86_64,
little-endian, ELFCLASS64), e guarda ponteiros para `.symtab`, `.strtab` e a
tabela de seções.

### Fase 2 — Tabela global de símbolos (`build_gsyms`)

Itera sobre todas as `.symtab` de todos os inputs e constrói um hash map
global `name → (input, índice)`. Símbolos com binding `STB_GLOBAL` ou
`STB_WEAK` entram. `STB_LOCAL` fica só dentro do próprio `.o` (não colidem
entre arquivos).

Erro clássico: `multiple definition of 'X'` quando dois `.o` definem o mesmo
símbolo. `STB_WEAK` é permitido, com regra de precedência: se já existe um
strong, o weak é ignorado.

### Fase 3 — Merge e layout (`merge_sections`)

Percorre cada `.o`, identifica as seções por nome (`.text`, `.rodata`,
`.data`, `.bss` e as variantes com sufixo), e as concatena em 4 seções de
saída, respeitando o `sh_addralign` de cada uma. Guarda em `SecMap[]` a
correspondência `(input_shdr → out_sec, out_off)` — sem ela, a Fase 4 é
impossível.

Layout: `[ELF header][program header][gap][.text][.rodata][.data][.bss]`.
Todos os endereços são calculados a partir de `BASE_ADDR = 0x400000`, com
offset de arquivo igual ao offset de vaddr (`vaddr = BASE_ADDR + file_offset`).
Isso elimina a matemática de alinhamento entre arquivo e memória.

O `.bss` ocupa memória mas não arquivo — essa diferença vira `p_filesz` vs
`p_memsz` no `PT_LOAD`.

### Fase 4 — Relocação (`apply_relocations`)

Para cada seção `.rela.*`, para cada `Rela`:

- `S` = endereço do símbolo (resolvido via `sym_addr` — recursivo se for UNDEF)
- `A` = addend da própria reloc (vem do `.o`)
- `P` = `vaddr_da_seção_final + out_off_da_seção_input + r_offset`

Aplica a fórmula da arquitetura e escreve o resultado no local (`loc`) dentro
da seção de saída já copiada.

Tipos suportados:

| Tipo | Fórmula | Uso |
|---|---|---|
| `R_X86_64_64` | `S + A` | ponteiros absolutos em `.data` |
| `R_X86_64_PC32` | `S + A − P` | calls e jumps locais |
| `R_X86_64_PLT32` | `S + A − P` | calls (tratado igual a PC32) |
| `R_X86_64_32` | `S + A` (32 bits) | dados 32-bit |
| `R_X86_64_32S` | `S + A` (32-bit signed) | idem |
| `R_X86_64_PC64` | `S + A − P` | PC-relativo 64-bit |
| `R_X86_64_GOTPCREL*` | relaxado para `lea` | ver abaixo |

**Sobre `GOTPCRELX`**: o LLVM, quando compila IR com `-fpic`, emite acesso a
globais via `mov rax, [rip + disp]` com reloc GOT-relativa. Como todos os
símbolos estão resolvidos localmente, o linker faz "relaxamento": troca o
opcode `8B` (mov) por `8D` (lea), o que faz a instrução carregar o *endereço*
do símbolo em vez do valor que está na GOT. Detecta o padrão por bytes
(`[REX.W] 8B <ModRM>` com `ModRM & 0xC7 == 0x05`) e funciona para qualquer
registrador destino.

### Fase 5 — Escrita (`write_output`)

Escreve um `ET_EXEC` com um único `PT_LOAD` RWX. O segmento é estendido em
`HEAP_FOLGA` (64 KB) bytes além do `.bss`, para dar espaço ao heap inicial.

Símbolos sintéticos definidos pelo linker (não vêm de nenhum `.o`):

| Símbolo | Valor |
|---|---|
| `_end` | `BASE_ADDR + g_mem_end` |
| `__bss_start` | `vaddr` do `.bss` |
| `__bss_end` | `vaddr + size` do `.bss` |
| `_edata` | `vaddr + size` do `.data` |

Esses são os mesmos símbolos que o `ld` define via linker script, e o `rt.c`
consulta `_end` para saber onde começa o heap.

## Integração com o CLI

```bash
# Pipeline padrão (clang faz tudo)
lumina build app.lm

# Pipeline com linker próprio
lumina build app.lm --linker=self
```

Quando `--linker=self` está presente, o `cmd_build` em
`lumina_cli/commands/build.py` faz:

1. Gera o `.ll` normalmente (lexer → parser → semantic → codegen LLVM).
2. `clang -c -fno-pic -fno-pie -fno-stack-protector app.ll -o app.o`
   (só compila, não linka).
3. `linker/lumina-ld linker/runtime/start.o app.o linker/runtime/rt.o -o app`.

Também força `--no-gc` implicitamente, porque a runtime `rt.c` implementa
`GC_malloc` como `malloc` sem coletor real — deixar o GC "ligado" só vazaria
memória.

Se `linker/lumina-ld` não existir, o comando falha com uma mensagem clara:
*"rode 'make' em linker/ antes de usar --linker=self"*.

## Runtime (`rt.c`)

A runtime freestanding fornece as funções externas que o codegen do Lumina
emite. Ela é compilada uma vez (`make` em `linker/`) e linkada em cada build.

### O que a runtime fornece

| Categoria | Símbolos |
|---|---|
| Memória | `malloc`, `free`, `calloc`, `memset`, `memcpy`, `memmove`, `memcmp` |
| Strings | `strlen`, `strcmp`, `strncmp`, `strcpy`, `strncpy`, `strcat`, `strstr`, `atoi` |
| I/O console | `printf`, `snprintf`, `putchar`, `getchar`, `fflush` |
| I/O arquivo | `fopen`, `fclose`, `fread`, `fwrite`, `fseek`, `ftell`, `fgets`, `fputs` |
| I/O fd | `open`, `close`, `read`, `write`, `lseek`, `remove` |
| Math | `pow`, `sqrt`, `abs`, `labs`, `floor`, `ceil`, `round` |
| Random | `rand`, `srand` |
| Tempo | `usleep` |
| Sinais | `abort` |
| Sockets | `socket`, `bind`, `listen`, `accept`, `connect`, `send`, `recv`, `setsockopt` |
| Epoll | `epoll_create1`, `epoll_ctl`, `epoll_wait` |
| GC shims | `GC_init`, `GC_malloc`, `GC_free` |

Tudo implementado direto sobre syscalls Linux (via `syscall` inline asm),
sem depender de libc.

### O que a runtime NÃO fornece

- **`pthread_create` e família** — implementar exige `clone()` + TLS +
  barreiras de sincronização. É projeto à parte.
- **`InitWindow` (raylib)** — biblioteca gráfica externa.
- **`js_alert` (WASM)** — target WASM não é ELF.
- **`cpp_print_hello` (FFI C++)** — precisa linkar `ffi_helper.o`.

## Limitações conhecidas

1. **Um único `PT_LOAD` RWX** — sem segregação W^X. Um dia isso vira dois
   segmentos (R+X para `.text`/`.rodata`, RW para `.data`/`.bss`).
2. **Sem `.eh_frame`** — não há unwinding de exceções C++. Não é problema
   porque Lumina não tem exceções C++.
3. **Sem GOT/PLT real** — tudo resolvido em tempo de link, sem indireção.
   Isso quebra se um dia houver `.so`.
4. **Sem TLS** — `thread_local` não funciona.
5. **Sem section headers no output** — `readelf -S` mostra nada. `readelf -h`,
   `-l` e `-s` funcionam.
6. **Só x86_64** — cross-compile exige um linker por arquitetura.

## Como debugar

O linker imprime tudo em stderr, então é seguro pipar stdout. Para investigar
um binário gerado:

```bash
# Verifica tipo, máquina, entry point
readelf -h app

# Verifica o segmento PT_LOAD (filesz vs memsz)
readelf -l app

# Desmonta o código
objdump -d app | head -60

# Se tiver .o (antes do link)
readelf -r app.o                       # relocações pendentes
objdump -dr app.o | head -80           # disassembly + relocações anotadas

# Se crashar em runtime
gdb -batch -ex run -ex "info registers rip rax" -ex "x/8i \$rip-16" app
```

Erros comuns e o que significam:

| Erro | Causa | Onde consertar |
|---|---|---|
| `undefined reference to 'X'` | runtime não define `X` | adicionar em `rt.c` |
| `reloc tipo N não suportada` | `.o` usa reloc não coberta | adicionar case em `apply_relocations` |
| `GOTPCRELX não relaxável` | padrão de instrução desconhecido | estender o if em `apply_relocations` |
| `PC32 fora de alcance` | jump > 2 GB | reestruturar layout (raro) |
| `multiple definition` | dois `.o` com o mesmo global | renomear ou `weak` |
| `símbolo de entrada '_start' não encontrado` | falta `runtime/start.o` na linha | verificar ordem dos inputs |

## Como estender

### Adicionar um símbolo à runtime

1. Abrir `linker/runtime/rt.c`.
2. Adicionar o prototype no bloco `forward declarations` no topo.
3. Adicionar a implementação no bloco apropriado (memória, strings, etc.).
4. Rebuild: `( cd linker && make clean && make )`.
5. Testar: `./linker/triagem.sh examples`.

### Adicionar um tipo de relocação

1. Abrir `linker/link.c`.
2. Adicionar o case no `switch (t)` dentro de `apply_relocations`.
3. Fórmula típica: `S + A` ou `S + A − P`. Ler a seção "Relocation Types" da
   x86_64 psABI para saber qual usar.
4. Rebuild e testar.

### Adicionar um símbolo sintético

1. Abrir `linker/link.c`, função `sym_addr`.
2. Adicionar o `if (!strcmp(name, "..."))` no bloco `SHN_UNDEF`.
3. Retornar o vaddr calculado.

## Arquivos

```
linker/
├── link.c              # o linker (lumina-ld)
├── Makefile            # build do lumina-ld + runtime
├── test.sh             # teste end-to-end manual
├── triagem.sh          # roda todos os exemplos via pipeline do linker
└── runtime/
    ├── start.S         # _start (assembly) + swapcontext/getcontext
    └── rt.c            # runtime freestanding
```

## Teste automatizado

Paridade com `clang` no `scripts/check_examples.sh --run`:

| Modo | PASS | SKIP | FAIL |
|---|---:|---:|---:|
| `clang` (padrão) | 54 | 17 | 0 |
| `lumina-ld` (self) | 54 | 17 | 0 |

Os 17 SKIP são idênticos nos dois modos — servidores que não terminam
sozinhos, alvos WASM, ou codegen bugs documentados. O `linker/triagem.sh`
tem uma medida complementar (linka + roda em todos os `.lm`, inclusive os
que o `check_examples.sh` pula por padrão):

```
PASS=56  FAIL-COMPILE=0  FAIL-LINK=0  FAIL-RUN=0  SKIP=15
```

Os 15 SKIP da triagem têm motivo documentado em
[`bugs.md`](../engineering/bugs.md#bugs-identificados-não-corrigidos):
1 módulo auxiliar, e 14 que dependem de subsistemas fora do escopo do linker
(pthread, raylib, FFI C++, WASM, servidores que não terminam).

Para rodar a triagem:

```bash
# Build do linker primeiro
( cd linker && make clean && make )

# Triagem completa
./linker/triagem.sh examples
```

## Referências

- **Linkers & Loaders**, John R. Levine — capítulos 2, 3, 4, 5.
- **x86_64 psABI**, seção "Relocation Types" — tabela canônica.
- **`man 5 elf`** — estrutura ELF.
- **`chibicc`**, Rui Ueyama — mini linker didático em `main.c`.
- **`mold`**, Rui Ueyama — linker de produção, código limpo.
