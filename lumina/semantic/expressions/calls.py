"""Chamadas: resolução de kwargs, builtins, métodos, genéricos."""
from ...ast import CallExpr, MemberExpr, VariableExpr
from ...builtins import BUILTIN_RET
from ...errors import LuminaError
from ..types import is_assignable, substitute_generic, unify_type, parse_fn_type
from .helpers import get_suggestion


class CallsMixin:

    def _resolve_kwargs(self, node, fn_def, skip_self=False):
        """Converte `node.kwargs` em `node.args` posicionais.

        Modifica `node` in-place. Após isso, o codegen só vê positional args.
        Parâmetros não fornecidos são preenchidos com seu default — se não
        houver default, é erro.
        """
        if not node.kwargs:
            return
        if fn_def is None:
            raise LuminaError(
                f"Argumentos nomeados não são suportados em "
                f"'{getattr(node.callee, 'name', '?')}'. "
                f"Use argumentos posicionais.",
                self.filename,
                getattr(node, 'line', 0) or 0,
                getattr(node, 'col', 0) or 0,
                self.source_code,
            )

        params = fn_def.params
        if skip_self and params:
            params = params[1:]

        param_names = [p.name for p in params]
        n = len(param_names)

        positional = list(node.args)
        base = positional[1:] if skip_self else positional

        if len(base) > n:
            return  # deixa o codegen reclamar

        new_args = [None] * n
        for i, a in enumerate(base):
            new_args[i] = a

        for name, val in node.kwargs:
            if name not in param_names:
                raise LuminaError(
                    f"Parâmetro '{name}' não existe.",
                    self.filename, 0, 0, self.source_code,
                )
            idx = param_names.index(name)
            if new_args[idx] is not None:
                raise LuminaError(
                    f"Argumento duplicado para '{name}'.",
                    self.filename, 0, 0, self.source_code,
                )
            new_args[idx] = val

        final_args = []
        for i in range(n):
            if new_args[i] is not None:
                final_args.append(new_args[i])
            else:
                default = getattr(params[i], 'default', None)
                if default is None:
                    raise LuminaError(
                        f"Parâmetro '{params[i].name}' é obrigatório.",
                        self.filename, 0, 0, self.source_code,
                    )
                final_args.append(default)

        if skip_self:
            node.args = [positional[0]] + final_args
        else:
            node.args = final_args
        node.kwargs = []

    def visit_CallExpr(self, node):
        func_name = None
        if isinstance(node.callee, MemberExpr):
            func_name = node.callee.member
        elif isinstance(node.callee, VariableExpr):
            func_name = node.callee.name

        # Resolve named arguments em posicional.
        if node.kwargs:
            if node.is_method:
                obj_node = node.args[0]
                obj_type = self.visit(obj_node)
                fn_def = None
                if obj_type and obj_type != "Unknown":
                    struct_name = obj_type.split('<')[0]
                    real_name = f"{struct_name}_{func_name}"
                    fn_def = self.function_defs.get(real_name)
                self._resolve_kwargs(node, fn_def, skip_self=True)
            else:
                fn_def = self.function_defs.get(func_name)
                self._resolve_kwargs(node, fn_def, skip_self=False)

        # `copy(s)` herda o tipo do argumento. Se o arg é `[float]`,
        # o resultado é `[float]` — não `[int]`.
        if func_name == "copy" and not node.is_method and node.args:
            arg_type = self.visit(node.args[0])
            if arg_type and isinstance(arg_type, str) \
                    and arg_type.startswith("[") and arg_type.endswith("]"):
                return arg_type
            # Fallback: assume [int]
            return "[int]"

        # Builtins com tipo de retorno conhecido (fonte única:
        # lumina/builtins.py::BUILTIN_RET).
        if not node.is_method:
            if func_name in BUILTIN_RET:
                for arg in node.args:
                    self.visit(arg)
                return BUILTIN_RET[func_name]

        # `obj.campo_fn(args)` — o "método" é na verdade um campo fn-typed.
        if (node.is_method
                and isinstance(node.callee, MemberExpr)
                and len(node.args) >= 1):
            obj_node = node.args[0]
            obj_type = self.visit(obj_node)
            if obj_type and obj_type != "Unknown":
                base_type = obj_type.split('<')[0]
                struct_def = self.struct_defs.get(base_type)
                if struct_def is not None and hasattr(struct_def, 'fields'):
                    field_type = struct_def.fields.get(func_name)
                    if field_type and (field_type == "fn" or field_type.startswith("fn(")):
                        sig = None
                        if field_type.startswith("fn("):
                            sig = parse_fn_type(field_type)
                        if sig is not None:
                            param_types, ret_type = sig
                            n_expected = len(param_types)
                            n_got = len(node.args) - 1
                            if n_got != n_expected:
                                raise LuminaError(
                                    f"Campo '{func_name}' espera {n_expected} "
                                    f"args, recebeu {n_got}.",
                                    self.filename, getattr(node, 'line', 0),
                                    getattr(node, 'col', 0), self.source_code,
                                )
                            for arg_node, expected in zip(node.args[1:], param_types):
                                actual = self.visit(arg_node)
                                if actual and not is_assignable(expected, actual):
                                    raise LuminaError(
                                        f"Tipo inválido para parâmetro de "
                                        f"'{func_name}': esperado '{expected}', "
                                        f"obteve '{actual}'.",
                                        self.filename, getattr(node, 'line', 0),
                                        getattr(node, 'col', 0), self.source_code,
                                    )
                            return ret_type if ret_type != "void" else None
                        for arg in node.args[1:]:
                            self.visit(arg)
                        return None

        if node.is_method:
            if not node.args:
                raise LuminaError(
                    f"Chamada de método '{func_name}' sem objeto alvo.",
                    self.filename, getattr(node, 'line', 0),
                    getattr(node, 'col', 0), self.source_code,
                )
            obj_node = node.args[0]
            obj_type = self.visit(obj_node)
            if not obj_type:
                return None
            if obj_type == "str":
                if func_name not in ("contains", "starts_with", "len",
                                     "upper", "lower"):
                    raise LuminaError(
                        f"Método de string '{func_name}' não suportado.",
                        self.filename, getattr(node, 'line', 0),
                        getattr(node, 'col', 0), self.source_code,
                    )
            elif obj_type != "Unknown":
                from ...common.mangle import mangle_method
                base_name = obj_type.split('<')[0]
                candidates = []
                if "<" in obj_type:
                    candidates.append(mangle_method(obj_type, func_name))
                candidates.append(f"{base_name}_{func_name}")

                if not any(c in self.functions for c in candidates):
                    raise LuminaError(
                        f"Método '{func_name}' não implementado para a struct "
                        f"'{base_name}'.",
                        self.filename, getattr(node, 'line', 0),
                        getattr(node, 'col', 0), self.source_code,
                    )
        else:
            # Chamada indireta via function pointer local.
            info = self.get_var_info(func_name) if func_name else None
            var_type = info.get('type') if info else None

            if var_type == 'fn':
                for arg in node.args:
                    self.visit(arg)
                return None

            if var_type and var_type.startswith("fn("):
                sig = parse_fn_type(var_type)
                if sig is not None:
                    param_types, ret_type = sig
                    n_expected = len(param_types)
                    n_got = len(node.args)
                    if n_got != n_expected:
                        raise LuminaError(
                            f"Função '{func_name}' espera {n_expected} args, "
                            f"recebeu {n_got}.",
                            self.filename, getattr(node, 'line', 0),
                            getattr(node, 'col', 0), self.source_code,
                        )
                    for arg_node, expected in zip(node.args, param_types):
                        actual = self.visit(arg_node)
                        if actual and not is_assignable(expected, actual):
                            raise LuminaError(
                                f"Tipo inválido para parâmetro de "
                                f"'{func_name}': esperado '{expected}', "
                                f"obteve '{actual}'.",
                                self.filename, getattr(node, 'line', 0),
                                getattr(node, 'col', 0), self.source_code,
                            )
                    return ret_type if ret_type != "void" else None

            if (func_name not in self.builtin_functions
                    and func_name not in self.functions):
                suggestion = get_suggestion(
                    func_name,
                    list(self.functions) + list(self.builtin_functions),
                )
                msg = f"Função '{func_name}' não declarada."
                if suggestion:
                    msg += f" Você quis dizer '{suggestion}'?"
                raise LuminaError(
                    msg, self.filename, getattr(node, 'line', 0),
                    getattr(node, 'col', 0), self.source_code,
                )

            if func_name in self.function_defs:
                fn_def = self.function_defs[func_name]

                required = sum(
                    1 for p in fn_def.params
                    if getattr(p, 'default', None) is None
                )
                n_args = len(node.args)
                if not (required <= n_args <= len(fn_def.params)):
                    if required == len(fn_def.params):
                        raise LuminaError(
                            f"Função '{func_name}' espera {required} args, "
                            f"recebeu {n_args}.",
                            self.filename, getattr(node, 'line', 0),
                            getattr(node, 'col', 0), self.source_code,
                        )
                    else:
                        raise LuminaError(
                            f"Função '{func_name}' espera entre {required} e "
                            f"{len(fn_def.params)} args, recebeu {n_args}.",
                            self.filename, getattr(node, 'line', 0),
                            getattr(node, 'col', 0), self.source_code,
                        )

                type_params = getattr(fn_def, 'type_params', None) or []

                if type_params:
                    # FIX 8: visitta cada arg UMA vez e reusa o tipo na
                    # validação. Antes, `self.visit(arg_node)` era chamado
                    # 2× (unificação + validação), duplicando efeitos
                    # colaterais como heap_allocs/freed_vars.
                    arg_types = [self.visit(a) for a in node.args]

                    type_map = {}
                    for arg_type, param in zip(arg_types, fn_def.params):
                        if arg_type is None:
                            continue
                        unify_type(param.type_ann, arg_type, type_map)

                    for arg_type, param in zip(arg_types, fn_def.params):
                        if arg_type is None:
                            continue
                        expected = substitute_generic(param.type_ann, type_map)
                        if expected != param.type_ann and expected.isupper():
                            continue
                        if not is_assignable(expected, arg_type):
                            raise LuminaError(
                                f"Tipo inválido para parâmetro '{param.name}': "
                                f"esperado '{expected}', obteve '{arg_type}'.",
                                self.filename, getattr(node, 'line', 0),
                                getattr(node, 'col', 0), self.source_code,
                            )
                else:
                    for arg_node, param in zip(node.args, fn_def.params):
                        arg_type = self.visit(arg_node)
                        p_name, p_type = param.name, param.type_ann
                        if (arg_type and p_type
                                and not is_assignable(p_type, arg_type)):
                            raise LuminaError(
                                f"Tipo inválido para parâmetro '{p_name}': "
                                f"esperado '{p_type}', obteve '{arg_type}'.",
                                self.filename, getattr(node, 'line', 0),
                                getattr(node, 'col', 0), self.source_code,
                            )

            # Rastreia variáveis liberadas com `free()`.
            if func_name == "free" and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, VariableExpr):
                    self.freed_vars.add(arg0.name)

        for arg in node.args:
            self.visit(arg)
        return None