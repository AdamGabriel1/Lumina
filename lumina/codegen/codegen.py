"""Composition root do codegen LLVM.

Os métodos foram divididos em mixins por área (setup, registration,
generics, traits, tco, function_body). A MRO abaixo garante que
`self.<qualquer_coisa>` resolve para a implementação correta.

Ordem da MRO (da esquerda para a direita):
  1. ExpressionCodegen     — visitors de expressão (literals, operators, ...)
  2. StatementCodegen      — visitors de statement (var_decl, control, flow, match)
  3. HelpersCodegen        — create_global_string, to_float_if_needed
  4. TypesCodegen          — get_llvm_type, get_llvm_param_type, monomorphized structs
  5. SetupMixin            — setup_libc_functions, _emit_mutable_global
  6. RegistrationMixin     — register_*, _apply_llvm_attrs, _llvm_ty_to_str
  7. GenericsMixin         — materialize_generic, _infer_type_map_lumina
  8. TraitsMixin           — _validate_macro (resolve_trait_defaults migrou p/ semantic)
  9. TCOMixin              — SCCs + dispatcher
 10. FunctionBodyMixin     — generate_function_body
"""
from ..builtins import BUILTIN_FUNCTIONS
from llvmlite import ir

from .expressions import ExpressionCodegen
from .statements import StatementCodegen
from .helpers import HelpersCodegen
from .types import TypesCodegen
from .setup import SetupMixin
from .registration import RegistrationMixin
from .generics import GenericsMixin
from .traits import TraitsMixin
from .tco import TCOMixin
from .function_body import FunctionBodyMixin

from ..ast import Function as AstFunction, TraitDecl, ExternDecl
from .context import normalize_attrs


class LLVMCodegen(
    ExpressionCodegen,
    StatementCodegen,
    HelpersCodegen,
    TypesCodegen,
    SetupMixin,
    RegistrationMixin,
    GenericsMixin,
    TraitsMixin,
    TCOMixin,
    FunctionBodyMixin,
):

    def __init__(self, target_triple=None, use_gc=True):
        # Contexto LLVM próprio por instância. Sem isso, `ir.Module()`
        # usa o `global_context` do llvmlite, e tipos identificados
        # (struct/enum) vazam entre instâncias — recompilar a mesma
        # struct dispara "P is already defined". Isso afetava o REPL.
        self.context = ir.Context()
        self.module = ir.Module(name="lumina_module", context=self.context)

        try:
            from llvmlite.binding import get_default_triple
            self.module.triple = target_triple or get_default_triple()
        except Exception:
            pass

        self.use_gc = use_gc

        self.i64_ty = ir.IntType(64)
        self.i32_ty = ir.IntType(32)
        self.f64_ty = ir.DoubleType()
        self.i8_ty = ir.IntType(8)
        self.voidptr_ty = self.i8_ty.as_pointer()
        self.void_ty = ir.VoidType()

        self.builder = None
        self.functions_table = {}
        self.function_defs = {}
        self.struct_types = {}
        self.struct_fields = {}
        self.struct_defs = {}
        self.symbol_table = {}
        self.var_types = {}
        self.global_var_decls = {}
        self.global_mut_vars = {}

        self.string_counter = 0
        self.lambda_counter = 0
        self._fn_wrappers = {}
        self.heap_allocs = set()

        self.builtin_functions = BUILTIN_FUNCTIONS

        self.loop_stack = []
        self.defer_stack = []
        self.current_body_bb = None

        self._safe_mode = False
        self.macros = {}

        self._current_scc_slots = None
        self._current_scc_ids = None
        self._current_scc_id_slot = None
        self._current_scc_dispatch_bb = None

        self.array_lengths = {}
        self.freed_vars = set()
        self.closure_vars = set()

        self.setup_libc_functions()
        self.alias_methods = set()

        self._deferred_globals = []

    # ==================================================================
    # Geração do módulo
    # ==================================================================
    def generate_module(self, ast):
        # ------------------------------------------------------------------
        # 0. Reset completo de estado por chamada.
        #
        # Se a mesma instância de LLVMCodegen for reusada (REPL, testes),
        # tudo isso precisa ser zerado. Sem isso, `struct_defs` acumula
        # entradas velhas e a Pass 0 vira no-op silencioso.
        # ------------------------------------------------------------------
        self.global_var_decls = {}
        self.global_mut_vars = {}
        self._deferred_globals = []
        self.struct_types = {}
        self.struct_fields = {}
        self.struct_defs = {}
        self.functions_table = {}
        self.function_defs = {}
        self.symbol_table = {}
        self.var_types = {}
        self.macros = {}
        self.alias_methods = set()

        # 0a. Coleta VarDecls de topo.
        for decl in ast:
            if type(decl).__name__ != 'VarDecl':
                continue
            is_mut = getattr(decl, 'is_mutable', False)
            has_value = getattr(decl, 'value', None) is not None

            # `mut X: T` no top-level é um global válido mesmo sem
            # inicializador — vira zero-init, atribuível depois.
            #
            # Antes, só VarDecl com `value` virava global; `mut node_kinds: ptr`
            # (sem `=`) era silenciosamente descartado e toda leitura caía em
            # `ir.Constant(i64, 0)`. Sintoma: variável sempre 0, writes no-op.
            if is_mut:
                self._emit_mutable_global(decl)
            elif has_value:
                # `let X = ...` no topo continua inline-constante (não vira
                # global — é constante de compilação).
                self.global_var_decls[decl.name] = decl

        # 0b. Coleta macros (@macro).
        for decl in ast:
            if isinstance(decl, AstFunction):
                attrs_norm = normalize_attrs(getattr(decl, 'attrs', None))
                if any(name == 'macro' for name, _args in attrs_norm):
                    self._validate_macro(decl)
                    self.macros[decl.name] = decl

        # ================================================================
        # FIX — Pass 0: pré-popula `struct_defs` com TODAS as decls de
        # struct/enum. Sem criar tipo LLVM ainda. Isso é o que permite
        # `register_struct` / `get_llvm_type` resolverem referências
        # a tipos que vêm de imports resolvidos DEPOIS no AST.
        #
        # Bug que este fix resolve: uma struct `A` cujo campo usa `B`
        # (ex: `struct Parser: tokens: TokenList`, com `TokenList` de
        # `lexer.lm` importado depois) tinha o campo tipado como `i64`
        # por fallback silencioso. Sintoma: `p.tokens.size` retornava
        # 0 mesmo após `p.tokens = tokens`.
        #
        # IMPORTANTE: este passo DEVE rodar antes de `register_function`
        # (Pass 2). Se rodar depois, `register_struct` já rodou com
        # `struct_defs` vazio para os tipos ainda-não-vistos.
        # ================================================================
        for decl in ast:
            if hasattr(decl, 'name') and (
                hasattr(decl, 'fields') or hasattr(decl, 'variants')
            ):
                self.struct_defs.setdefault(decl.name, decl)

        # Pass 1: registra de verdade. `register_struct` e
        # `register_enum` são idempotentes.
        for decl in ast:
            if hasattr(decl, 'name') and decl.name in self.struct_types:
                continue
            if hasattr(decl, 'fields') and not hasattr(decl, 'variants'):
                self.register_struct(decl)
            elif hasattr(decl, 'variants'):
                self.register_enum(decl)

        # 2. Pré-registra todas as funções e métodos de impls.
        # TraitDecl NÃO é registrado.
        # Macros NÃO são registradas como funções normais.
        # Externs que colidem com builtins NÃO são registrados.
        for decl in ast:
            if isinstance(decl, TraitDecl):
                continue
            if hasattr(decl, 'params') and hasattr(decl, 'return_type'):
                if isinstance(decl, AstFunction) and decl.name in self.macros:
                    continue
                if isinstance(decl, ExternDecl) and decl.name in self.builtin_functions:
                    continue
                self.register_function(decl)
            elif hasattr(decl, 'methods'):
                for method in decl.methods:
                    self.register_function(method)

        # 2.5 Registra aliases `metodo` → `Struct_metodo` para traits.
        for decl in ast:
            if not (hasattr(decl, 'methods') and hasattr(decl, 'struct_name')):
                continue
            trait_name = getattr(decl, 'trait_name', None)
            if not trait_name:
                continue
            for method in decl.methods:
                parts = method.name.split('_', 1)
                if len(parts) == 2:
                    short = parts[1]
                    full_entry = self.functions_table.get(method.name)
                    if full_entry:
                        self.functions_table[short] = full_entry
                        self.alias_methods.add(short)

        # 3. Detecta SCCs de tail calls (mutual recursion) e gera dispatchers.
        sccs = self._compute_tail_call_sccs(ast)
        handled_scc_members = set()
        for scc_id, members in enumerate(sccs):
            funcs = [
                d for d in ast
                if isinstance(d, AstFunction)
                and d.name in members
                and not getattr(d, 'type_params', None)
            ]
            if len(funcs) < 2:
                continue
            if not self._can_dispatcher(funcs):
                continue
            self._materialize_scc_dispatcher(scc_id, funcs)
            handled_scc_members.update(f.name for f in funcs)

        # 3b. Gera o corpo das funções restantes.
        for decl in ast:
            if isinstance(decl, TraitDecl):
                continue
            if hasattr(decl, 'body') and decl.body is not None:
                if getattr(decl, 'type_params', None):
                    continue
                if isinstance(decl, AstFunction) and decl.name in self.macros:
                    continue
                if isinstance(decl, AstFunction) and decl.name in handled_scc_members:
                    continue
                self.generate_function_body(decl)
            elif hasattr(decl, 'methods'):
                for method in decl.methods:
                    if hasattr(method, 'body') and method.body is not None:
                        if getattr(method, 'type_params', None):
                            continue
                        self.generate_function_body(method)

        return str(self.module)

    # ==================================================================
    # API de baixo nível
    # ==================================================================
    def codegen_stmt(self, node):
        return self.visit(node)

    def codegen_expr(self, node):
        return self.visit(node)

    # ==================================================================
    # Hooks de Correção de Codegen
    # ==================================================================
    def _reset_function_codegen_state(self):
        self._fn_entry_block = None
        self._fn_return_type = None

    def _fn_emit_alloca(self, name, ty):
        """Emite um `alloca` no **fim do entry block**, antes do terminador.

        PATCH v3: usa `opname` (API estável do llvmlite) em vez de
        `is_terminator` (que não existe como propriedade pública).

        Motivo de inserir no fim do entry block (não no início):
        `_deferred_globals` são inicializadas no entry_bb, e precisam
        ficar ANTES de qualquer alloca de temporário.
        """
        if self._fn_entry_block is None:
            return self.builder.alloca(ty, name=name)

        current_block = self.builder.block
        entry = self._fn_entry_block

        _TERMINATORS = {
            'br', 'ret', 'unreachable', 'switch', 'invoke',
            'resume', 'indirectbr', 'callbr', 'catchswitch',
            'cleanupret', 'catchret',
        }

        if len(entry.instructions) > 0:
            last = entry.instructions[-1]
            if getattr(last, 'opname', None) in _TERMINATORS:
                self.builder.position_before(last)
            else:
                self.builder.position_at_end(entry)
        else:
            self.builder.position_at_end(entry)

        ptr = self.builder.alloca(ty, name=name)
        self.builder.position_at_end(current_block)
        return ptr

    def _fn_ensure_terminator(self):
        """Garante que o bloco atual termine com um terminador."""
        if self.builder.block.is_terminated:
            return

        ret_ty = self._fn_return_type

        if ret_ty is None or isinstance(ret_ty, ir.VoidType):
            self.builder.ret_void()
            return

        if isinstance(ret_ty, ir.LiteralStructType) and len(ret_ty.elements) == 0:
            self.builder.ret(ir.Constant(ret_ty, []))
            return

        try:
            self.builder.ret(self._zero_for_type(ret_ty))
        except Exception:
            self.builder.ret_void()