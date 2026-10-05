"""Orquestrador da análise semântica."""
from ..builtins import BUILTIN_FUNCTIONS
from ..common.attrs import normalize_attrs
from lumina.ast.statements import ErrorNode
from ..ast import (
    Function, ExternDecl, StructDecl, EnumDecl, ImplBlock,
    VarDecl, VariableExpr, TraitDecl, MatchStmt, TypeAlias,
    IfStmt, WhileStmt, ForStmt, DeferStmt, BenchStmt,
    LambdaExpr, CastExpr, MacroCallStmt,
)
from ..errors import LuminaError
from .expressions import ExpressionAnalyzer
from .statements import StatementAnalyzer
from .derives import DerivesMixin
from .trait_resolution import TraitResolutionMixin
from .types import expand_type_alias
from ..common.mangle import mangle_method


class SemanticAnalyzer(
    ExpressionAnalyzer,
    StatementAnalyzer,
    DerivesMixin,
    TraitResolutionMixin,
):

    def __init__(self, filename="program.lm", source_code=""):
        self.scopes = [{}]
        self.functions = set()
        self.function_defs = {}
        self.structs = set()
        self.struct_defs = {}
        self.filename = filename
        self.source_code = source_code
        self.heap_allocs = set()
        self.escapes = set()
        self.definition_locations = {}

        self.builtin_functions = BUILTIN_FUNCTIONS

        self.freed_vars = set()
        self.macros = {}
        self.type_aliases = {}

        # FIX (Fase 8): mapeia nome de variável → tipo Lumina do
        # elemento. Populado em `_analyze_var_decl` quando o valor é
        # um `ArrayExpr`. Consultar em `visit_IndexExpr` para inferir
        # o tipo do elemento.
        #
        # Cobre apenas variáveis locais e top-level. Não propaga por
        # parâmetros, retornos ou campos de struct — esses casos
        # continuam retornando `None` (comportamento anterior).
        self.array_elem_types = {}

    # ------------------------------------------------------------------
    # Análise principal
    # ------------------------------------------------------------------
    def analyze(self, declarations):
        self._expand_derives(declarations)
        self._resolve_trait_defaults(declarations)

        # Passada 0: coletar e expandir type aliases.
        self.type_aliases = {}
        for decl in declarations:
            if isinstance(decl, TypeAlias):
                params = list(getattr(decl, 'type_params', None) or [])
                self.type_aliases[decl.name] = (params, decl.target_type)

        if self.type_aliases:
            self._expand_type_aliases(declarations)

        # Passada 0: coletar macros.
        self.macros = {}
        for decl in declarations:
            if isinstance(decl, Function):
                for name, _args in normalize_attrs(getattr(decl, 'attrs', None)):
                    if name == 'macro':
                        self.macros[decl.name] = decl
                        break

        # Passada 1: registrar símbolos.
        for decl in declarations:
            if isinstance(decl, ErrorNode):
                continue
            if isinstance(decl, (Function, ExternDecl)):
                self.functions.add(decl.name)
                self.function_defs[decl.name] = decl
                if hasattr(decl, 'line'):
                    self.definition_locations[decl.name] = (
                        self.filename, decl.line, decl.col,
                    )
            elif isinstance(decl, StructDecl):
                self.structs.add(decl.name)
                self.struct_defs[decl.name] = decl
            elif isinstance(decl, EnumDecl):
                self.structs.add(decl.name)
                self.struct_defs[decl.name] = decl
                for v_name, _ in decl.variants:
                    self.functions.add(v_name)
            elif isinstance(decl, ImplBlock):
                for method in decl.methods:
                    self.functions.add(method.name)
                    self.function_defs[method.name] = method

                if decl.trait_name:
                    trait_def = next(
                        (d for d in declarations
                         if isinstance(d, TraitDecl) and d.name == decl.trait_name),
                        None,
                    )
                    if not trait_def:
                        raise LuminaError(
                            f"Trait '{decl.trait_name}' não declarada.",
                            self.filename, 0, 0, self.source_code,
                        )

                    for trait_method in trait_def.methods:
                        expected_name = mangle_method(decl.struct_name, trait_method.name)
                        if (expected_name not in self.functions
                                and not trait_method.body):
                            raise LuminaError(
                                f"Struct '{decl.struct_name}' não implementa o "
                                f"método '{trait_method.name}' exigido pelo "
                                f"Trait '{decl.trait_name}'.",
                                self.filename, getattr(decl, 'line', 0),
                                getattr(decl, 'col', 0), self.source_code,
                            )
                        impl_method = self.function_defs.get(expected_name)
                        if (impl_method
                                and impl_method.return_type != trait_method.return_type):
                            raise LuminaError(
                                f"Assinatura incorreta para "
                                f"'{trait_method.name}'. Esperado retorno "
                                f"'{trait_method.return_type}', mas obteve "
                                f"'{impl_method.return_type}'.",
                                self.filename, getattr(decl, 'line', 0),
                                getattr(decl, 'col', 0), self.source_code,
                            )

        # Passada 2: VarDecls de topo (globais)
        for decl in declarations:
            if isinstance(decl, VarDecl):
                if decl.var_type is not None:
                    base_type = decl.var_type.split('<')[0]
                    is_fn_sig = base_type.startswith("fn(")
                    if (base_type not in ("int", "float", "bool", "str", "ptr", "fn")
                            and not is_fn_sig
                            and base_type not in self.structs):
                        raise LuminaError(
                            f"Tipo '{decl.var_type}' não declarado.",
                            self.filename, getattr(decl, 'line', 0),
                            getattr(decl, 'col', 0), self.source_code,
                        )
                if decl.value:
                    self.visit(decl.value)
                self.declare_var(decl.name, decl.var_type, decl.is_mutable)
                if hasattr(decl, 'line'):
                    self.definition_locations[decl.name] = (
                        self.filename, decl.line, decl.col,
                    )

        # Passada 3: corpos de funções e métodos de impl.
        #
        # ADR 0003: corpos de macros são **pulados**. Usam
        # `quote:`/`~`/`~@`/`gensym` — construções que não têm
        # semântica de runtime. A expansão em si gera AST que será
        # analisada/gerada no call site.
        for decl in declarations:
            if isinstance(decl, Function):
                if decl.name in self.macros:
                    continue
                self.analyze_function(decl)
            elif isinstance(decl, ImplBlock):
                for method in decl.methods:
                    self.analyze_function(method)

    # ------------------------------------------------------------------
    # Escopo
    # ------------------------------------------------------------------
    def push_scope(self):
        self.scopes.append({})

    def pop_scope(self):
        self.scopes.pop()

    def declare_var(self, name, var_type, is_mutable):
        self.scopes[-1][name] = {'type': var_type, 'mutable': is_mutable}

    def get_var_info(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def _expand_type_aliases(self, declarations):
        """Reescreve TODOS os tipos do AST expandindo type aliases."""
        aliases = self.type_aliases

        def expand(t):
            if not isinstance(t, str):
                return t
            return expand_type_alias(t, aliases)

        def walk(node, seen=None):
            if node is None:
                return
            if seen is None:
                seen = set()
            node_id = id(node)
            if node_id in seen:
                return
            seen.add(node_id)

            if isinstance(node, (list, tuple)):
                for item in node:
                    walk(item, seen)
                return

            if isinstance(node, LambdaExpr):
                for p in node.params:
                    p.type_ann = expand(p.type_ann)
                node.return_type = expand(node.return_type)
                walk(node.body, seen)
                return

            if isinstance(node, CastExpr):
                node.target_type = expand(node.target_type)
                walk(node.expr, seen)
                return

            if isinstance(node, VarDecl):
                if node.var_type is not None:
                    node.var_type = expand(node.var_type)
                walk(node.value, seen)
                return

            if isinstance(node, StructDecl):
                for fname in list(node.fields.keys()):
                    node.fields[fname] = expand(node.fields[fname])
                return

            if isinstance(node, EnumDecl):
                new_variants = []
                for vname, payloads in node.variants:
                    if isinstance(payloads, list):
                        new_variants.append(
                            (vname, [expand(t) for t in payloads])
                        )
                    elif payloads:
                        new_variants.append((vname, expand(payloads)))
                    else:
                        new_variants.append((vname, payloads))
                node.variants = new_variants
                return

            if isinstance(node, (Function, ExternDecl, TraitDecl, ImplBlock)):
                params = getattr(node, 'params', None)
                if params is not None:
                    for p in params:
                        if hasattr(p, 'type_ann'):
                            p.type_ann = expand(p.type_ann)
                ret = getattr(node, 'return_type', None)
                if ret is not None:
                    node.return_type = expand(ret)
                methods = getattr(node, 'methods', None)
                if methods is not None:
                    walk(methods, seen)
                body = getattr(node, 'body', None)
                if body is not None:
                    walk(body, seen)
                return

            if hasattr(node, '__dataclass_fields__'):
                for fname in node.__dataclass_fields__:
                    if fname in ('line', 'col'):
                        continue
                    walk(getattr(node, fname, None), seen)

        for decl in declarations:
            walk(decl)

    def check_escape(self, node):
        if isinstance(node, VariableExpr) and node.name in self.heap_allocs:
            self.escapes.add(node.name)

    # ------------------------------------------------------------------
    # Análise de funções
    # ------------------------------------------------------------------
    def analyze_function(self, node: Function):
        saved_scopes = self.scopes
        global_scope = saved_scopes[0] if saved_scopes else {}
        self.scopes = [global_scope.copy()]

        saved_func_name = getattr(self, 'current_func_name', None)
        saved_ret_type = getattr(self, 'current_ret_type', None)

        try:
            self.current_ret_type = node.return_type
            self.current_func_name = node.name

            for param in node.params:
                self.declare_var(param.name, param.type_ann, True)

            for stmt in node.body:
                self.analyze_stmt(stmt)
        finally:
            self.scopes = saved_scopes
            self.current_func_name = saved_func_name
            self.current_ret_type = saved_ret_type

    # ------------------------------------------------------------------
    # Análise de MatchStmt (exaustividade)
    # ------------------------------------------------------------------
    def analyze_stmt(self, node):
        if isinstance(node, MatchStmt):
            cond_type = self.visit(node.condition)
            if cond_type and cond_type in self.struct_defs:
                struct_def = self.struct_defs[cond_type]
                if hasattr(struct_def, 'variants'):
                    if not node.default:
                        covered = []
                        for c in node.cases:
                            v = c[0]
                            if isinstance(v, list):
                                covered.extend(v)
                            elif v is not None:
                                covered.append(v)

                        all_variants = [v[0] for v in struct_def.variants]
                        missing = set(all_variants) - set(covered)
                        has_wildcard = any(c[0] is None for c in node.cases)
                        if missing and not has_wildcard:
                            raise LuminaError(
                                "Match não exaustivo. Faltam variantes ou um "
                                "ramo 'default'.",
                                self.filename, getattr(node, 'line', 0),
                                getattr(node, 'col', 0), self.source_code,
                            )

        super().analyze_stmt(node)