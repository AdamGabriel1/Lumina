"""Constantes de layout e política do codegen.

Magic numbers que aparecem em mais de um arquivo do codegen — ou que
representam **política ajustável** — ficam aqui. Números verdadeiramente
locais (um único call site) não migram.

Usado por:
  - `lumina/codegen/statements/var_decl.py`
  - `lumina/codegen/expressions/methods.py`
  - `lumina/codegen/expressions/aggregates.py`
  - `lumina/codegen/helpers.py`
"""

# ---------------------------------------------------------------------
# Tamanhos de tipos LLVM (em bytes)
# ---------------------------------------------------------------------
I64_BYTES = 8
"""Tamanho de um i64 em bytes. Usado em sizeof() de structs dinâmicas."""

# ---------------------------------------------------------------------
# Layout de structs alocadas
# ---------------------------------------------------------------------
MIN_ENUM_SIZE = 16
"""Tamanho mínimo alocado para um enum.

Layout de enum em Lumina: `{ i32 tag, payload_0, ..., payload_N }`.
Como `payload_i` são i64 (8 bytes), o tamanho é
`I64_BYTES + max_payloads * I64_BYTES` — o tag ocupa 8 bytes por
alinhamento. Se só há uma payload: 16. Se zero: 16 (tag + padding).
O mínimo garante que `malloc(16)` devolva um bloco redondo, evitando
writes em endereços não alinhados quando o slot é `payload_0`.
"""

CLOSURE_BLOCK_SIZE = 16
"""Tamanho do bloco de closure: `{ i8* fn_ptr, i8* env_ptr }`.

Dois ponteiros de 8 bytes cada. Toda lambda — com ou sem captura —
aloca exatamente este bloco no heap. O `env_ptr` é NULL quando não
há capturas.
"""

# ---------------------------------------------------------------------
# Escape analysis
# ---------------------------------------------------------------------
STACK_ALLOC_LIMIT = 4096
"""Número máximo de **elementos** para promover `alloc(N)` a `alloca`.

Acima disso, `alloc(N)` com `N` literal cai no GC (ou malloc em
`--no-gc`). Abaixo, o array vai para a stack. 4096 i64 = 32 KB por
frame — cabe confortavelmente num frame típico (8 MB) mesmo com
recursão moderada.

Ajustar este limite muda o trade-off:
  - Maior: menos pressão no GC, mais uso de stack.
  - Menor: mais pressão no GC, mais seguro em recursão profunda.
"""
