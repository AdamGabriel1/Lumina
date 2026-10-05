"""Expansão de `@derive(...)`.

  - Eq        → `fn {Struct}___eq__(a, b) -> bool`
  - PartialEq → `__eq__` E `__ne__` (habilita `==` e `!=`)
  - Debug     → `fn {Struct}___debug__(p) -> str`
  - Display   → alias de Debug
  - Clone     → `fn {Struct}_clone(self) -> {Struct}`
  - Default   → `fn new_{Struct}() -> {Struct}` (função livre)

Chamado no topo de `SemanticAnalyzer.analyze`, antes de qualquer
outra análise. Modifica `declarations` in-place, inserindo ImplBlocks
e Functions sintéticas.
"""
from ..ast import (
    Function, Param, ImplBlock,
    AssignStmt, MemberExpr, VariableExpr, ReturnStmt, VarDecl,
    BinaryExpr, CallExpr, IfStmt, BoolExpr, NumberExpr, StringExpr,
    UnaryExpr,
)
from ..common.attrs import normalize_attrs   # FIX 6
from ..errors import LuminaError              # FIX 11


class DerivesMixin:

    def _expand_derives(self, declarations):
        """Expande @derive(Eq, Debug, Default, Clone, Display) em
        métodos sintetizados (ImplBlocks) e funções livres.

        FIX 11: `@derive` em enum não é suportado (ainda). Antes era
        silenciosamente ignorado — o usuário escrevia `@derive(Eq)`
        num enum e nada acontecia. Agora é erro explícito.
        """
        new_decls = []
        for decl in declarations:
            # FIX 6: aceita List[str] e List[Tuple[str, List]].
            attrs = normalize_attrs(getattr(decl, 'attrs', None))
            if not attrs:
                continue

            # FIX 11: enum + @derive → erro explícito.
            is_enum = hasattr(decl, 'variants')
            is_struct = hasattr(decl, 'fields')
            if is_enum and not is_struct:
                for name, _args in attrs:
                    if name == 'derive':
                        raise LuminaError(
                            message=(
                                f"@derive em enum '{decl.name}' ainda não é "
                                f"suportado. Implemente os métodos "
                                f"manualmente (impl {decl.name}: ...)."
                            ),
                            filename=getattr(self, 'filename', '<semantic>'),
                            line=getattr(decl, 'line', 0) or 0,
                            col=getattr(decl, 'col', 0) or 0,
                            source_code=getattr(self, 'source_code', '') or '',
                        )
                continue

            # Só struct a partir daqui.
            if not is_struct:
                continue

            struct_name = decl.name
            methods = []   # métodos → ImplBlock
            free_fns = []  # funções livres → Function

            # Coleta todos os derives do @derive(...)
            derives = set()
            for attr_name, attr_args in attrs:
                if attr_name != 'derive':
                    continue
                for deriv in attr_args:
                    derives.add(deriv)

            # `PartialEq` gera __eq__ E __ne__ (equivalente ao `==`
            # e `!=`). `Eq` gera apenas __eq__.
            if 'Eq' in derives or 'PartialEq' in derives:
                methods.append(self._gen_eq(struct_name, decl))
            if 'PartialEq' in derives:
                methods.append(self._gen_ne(struct_name, decl))
            if 'Debug' in derives or 'Display' in derives:
                methods.append(self._gen_debug(struct_name, decl))
            if 'Clone' in derives:
                methods.append(self._gen_clone(struct_name, decl))
            if 'Default' in derives:
                free_fns.append(self._gen_default(struct_name, decl))

            if methods:
                new_decls.append(ImplBlock(struct_name, methods))
            new_decls.extend(free_fns)

        declarations.extend(new_decls)

    def _gen_eq(self, struct_name, struct_decl):
        """Gera: fn {Struct}___eq__(a, b) -> bool"""
        a_var = VariableExpr('a', 0, 0)
        b_var = VariableExpr('b', 0, 0)

        conditions = []
        for fname in struct_decl.fields.keys():
            a_field = MemberExpr(a_var, fname)
            b_field = MemberExpr(b_var, fname)
            conditions.append(BinaryExpr('==', a_field, b_field))

        if not conditions:
            cond = BoolExpr(True)
        elif len(conditions) == 1:
            cond = conditions[0]
        else:
            cond = conditions[0]
            for c in conditions[1:]:
                cond = BinaryExpr('and', cond, c)

        then_body = [ReturnStmt([BoolExpr(True)])]
        if_stmt = IfStmt(cond, then_body, None)
        return_stmt = ReturnStmt([BoolExpr(False)])

        mangled_name = f"{struct_name}___eq__"

        return Function(
            mangled_name,
            [Param('a', struct_name), Param('b', struct_name)],
            'bool',
            [if_stmt, return_stmt],
        )

    def _gen_ne(self, struct_name, struct_decl):
        """Gera: fn {Struct}___ne__(a, b) -> bool"""
        a_var = VariableExpr('a', 0, 0)
        b_var = VariableExpr('b', 0, 0)

        eq_callee = VariableExpr(f'{struct_name}___eq__', 0, 0)
        eq_call = CallExpr(eq_callee, [a_var, b_var])

        not_eq = UnaryExpr('not', eq_call)
        then_body = [ReturnStmt([BoolExpr(True)])]
        if_stmt = IfStmt(not_eq, then_body, None)

        return_stmt = ReturnStmt([BoolExpr(False)])

        mangled_name = f"{struct_name}___ne__"

        return Function(
            mangled_name,
            [Param('a', struct_name), Param('b', struct_name)],
            'bool',
            [if_stmt, return_stmt],
        )

    def _gen_debug(self, struct_name, struct_decl):
        """Gera: fn {Struct}___debug__(p: Struct) -> str"""
        p_var = VariableExpr('p', 0, 0)
        parts = [StringExpr(f"{struct_name} {{ ")]

        for i, fname in enumerate(struct_decl.fields.keys()):
            if i > 0:
                parts.append(StringExpr(", "))
            parts.append(StringExpr(f"{fname}: "))
            field_access = MemberExpr(p_var, fname)
            parts.append(field_access)

        parts.append(StringExpr(" }"))

        expr = parts[0]
        for p in parts[1:]:
            expr = BinaryExpr('+', expr, p)

        mangled_name = f"{struct_name}___debug__"

        return Function(
            mangled_name,
            [Param('p', struct_name)],
            'str',
            [ReturnStmt([expr])],
        )

    def _gen_clone(self, struct_name, struct_decl):
        """Gera: fn {Struct}_clone(self) -> {Struct}"""
        result_var = 'result'
        result_decl = VarDecl(result_var, struct_name, None, True)

        body = [result_decl]
        self_var = VariableExpr('self', 0, 0)
        result_ref = VariableExpr(result_var, 0, 0)

        for fname in struct_decl.fields.keys():
            lhs = MemberExpr(result_ref, fname)
            rhs = MemberExpr(self_var, fname)
            body.append(AssignStmt(lhs, rhs))

        body.append(ReturnStmt([VariableExpr(result_var, 0, 0)]))

        mangled_name = f"{struct_name}_clone"
        return Function(mangled_name, [Param('self', struct_name)],
                        struct_name, body)

    def _gen_default(self, struct_name, struct_decl):
        """Gera: fn new_{Struct}() -> {Struct} com todos os campos zerados."""
        result_var = 'result'
        result_decl = VarDecl(result_var, struct_name, None, True)

        body = [result_decl]
        result_ref = VariableExpr(result_var, 0, 0)

        for fname, ftype in struct_decl.fields.items():
            lhs = MemberExpr(result_ref, fname)

            if ftype == "float":
                rhs = NumberExpr("0.0", is_float=True)
            elif ftype == "bool":
                rhs = BoolExpr(False)
            elif ftype == "str":
                rhs = StringExpr("")
            else:
                rhs = NumberExpr("0", is_float=False)

            body.append(AssignStmt(lhs, rhs))

        body.append(ReturnStmt([VariableExpr(result_var, 0, 0)]))

        return Function(f"new_{struct_name}", [], struct_name, body)