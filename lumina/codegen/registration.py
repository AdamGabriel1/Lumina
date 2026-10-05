"""Registro de structs, enums e funções no módulo LLVM.

Também contém a aplicação de atributos LLVM (`@inline`, `@cold`, ...)
e o helper `_llvm_ty_to_str` usado por outros mixins.
"""
from llvmlite import ir
from ..common.attrs import normalize_attrs
from ..common.mangle import mangle_type
from ..errors import LuminaError


class RegistrationMixin:

    # ==================================================================
    # Registro de structs/enums/funções
    # ==================================================================
    def register_struct(self, node):
        if node.name in self.struct_types:
            return
        struct_ty = self.module.context.get_identified_type(node.name)
        self.struct_types[node.name] = struct_ty
        self.struct_defs[node.name] = node

        field_tys = []
        for ft in node.fields.values():
            # ----------------------------------------------------------
            # On-demand: se o campo referencia uma struct/enum que está
            # em `struct_defs` mas ainda não foi registrada em
            # `struct_types`, registra agora.
            #
            # Sem isto, `get_llvm_type(ft)` retornava `i64` (fallback)
            # quando `struct_defs` ainda não tinha o tipo. Com o
            # `struct_defs` pré-populado (Pass 0 em generate_module) e
            # este on-demand, a resolução funciona mesmo quando o tipo
            # é definido em arquivo importado resolvido depois.
            #
            # `.as_pointer()` é obrigatório: structs Lumina são passadas
            # por ponteiro em campos de struct. Sem o cast, o campo
            # fica struct-by-value e `ir.Constant` do phi da safe-nav
            # quebra com "int is not iterable".
            # ----------------------------------------------------------
            if ft not in self.struct_types and ft in self.struct_defs:
                sub_decl = self.struct_defs[ft]
                if hasattr(sub_decl, 'variants'):
                    self.register_enum(sub_decl)
                elif hasattr(sub_decl, 'fields'):
                    self.register_struct(sub_decl)

            if ft in self.struct_types:
                field_tys.append(self.struct_types[ft].as_pointer())
            else:
                field_tys.append(self.get_llvm_type(ft))

        struct_ty.set_body(*field_tys)
        self.struct_fields[node.name] = {
            name: i for i, name in enumerate(node.fields.keys())
        }

    def _enum_max_payloads(self, node):
        """Descobre o número máximo de payloads entre as variantes de um enum."""
        max_p = 0
        for variant in node.variants:
            if len(variant) < 2:
                continue
            v_payloads = variant[1]
            if isinstance(v_payloads, list):
                max_p = max(max_p, len(v_payloads))
            elif v_payloads is not None:
                max_p = max(max_p, 1)
        return max_p

    def register_enum(self, node):
        if node.name in self.struct_types:
            return

        if getattr(node, 'type_params', None):
            self.struct_defs[node.name] = node
            return

        struct_ty = self.module.context.get_identified_type(node.name)
        self.struct_types[node.name] = struct_ty
        self.struct_defs[node.name] = node

        max_p = self._enum_max_payloads(node)
        fields = [ir.IntType(32)] + [ir.IntType(64)] * max_p
        struct_ty.set_body(*fields)

        fields_map = {"tag": 0}
        for i in range(max_p):
            fields_map[f"payload_{i}"] = i + 1
        if max_p >= 1:
            fields_map["payload"] = 1
        self.struct_fields[node.name] = fields_map

    def register_function(self, node):
        if getattr(node, 'type_params', None):
            self.function_defs[node.name] = node
            return

        func_name = (
            getattr(node, 'module_prefix', '') + node.name
            if hasattr(node, 'module_prefix') else node.name
        )

        if func_name in self.functions_table:
            return

        if (func_name == "main"
                and len(node.params) == 0
                and node.return_type in ("int", "void")):
            i8pp_ty = self.i8_ty.as_pointer().as_pointer()
            func_type = ir.FunctionType(self.i32_ty, [self.i32_ty, i8pp_ty])
            func = ir.Function(self.module, func_type, name="main")
            self.functions_table[func_name] = (func, func_type)
            self.functions_table[node.name] = (func, func_type)
            self.function_defs[node.name] = node

            if "__lumina_argc" not in self.module.globals:
                argc_gv = ir.GlobalVariable(
                    self.module, self.i32_ty, name="__lumina_argc",
                )
                argc_gv.initializer = ir.Constant(self.i32_ty, 0)
            if "__lumina_argv" not in self.module.globals:
                argv_gv = ir.GlobalVariable(
                    self.module, i8pp_ty, name="__lumina_argv",
                )
                argv_gv.initializer = ir.Constant(i8pp_ty, None)
            return

        ret_ty = self.get_llvm_param_type(node.return_type)
        param_types = []
        for p in node.params:
            p_type = p.type_ann
            p_ty = self.get_llvm_param_type(p_type)
            param_types.append(p_ty)

        func_type = ir.FunctionType(ret_ty, param_types)
        func = ir.Function(self.module, func_type, name=func_name)
        self.functions_table[func_name] = (func, func_type)
        self.functions_table[node.name] = (func, func_type)
        self.function_defs[node.name] = node

        attrs = getattr(node, 'attrs', None) or []
        self._apply_llvm_attrs(func, attrs)

    def _apply_llvm_attrs(self, func, attrs):
        """
        Aplica atributos LLVM a `func`.

        Aceita `attrs` em `List[str]` ou `List[Tuple[str, List]]` —
        `normalize_attrs` padroniza. Mapeamento:
          @inline    → alwaysinline
          @noinline  → noinline
          @cold      → cold
          @hot       → inlinehint (aproximação — ver nota)
        """
        attrs_norm = normalize_attrs(attrs)
        names = {name for name, _args in attrs_norm}

        if 'inline' in names and 'noinline' in names:
            raise LuminaError(
                message=(
                    f"Atributos conflitantes em '{func.name}': "
                    f"@inline e @noinline são mutuamente exclusivos."
                ),
                filename=getattr(self, 'current_filename', '<compiler>'),
                line=0, col=0,
                source_code="",
            )

        _MAP = {
            'inline':   'alwaysinline',
            'noinline': 'noinline',
            'cold':     'cold',
            'hot':      'inlinehint',
        }

        for name, _args in attrs_norm:
            llvm_attr = _MAP.get(name)
            if llvm_attr:
                func.attributes.add(llvm_attr)

    # ==================================================================
    # Conversão LLVM → Lumina
    # ==================================================================
    def _llvm_ty_to_str(self, t):
        if t == self.i64_ty:
            return "int"
        if isinstance(t, ir.IntType) and t.width == 8:
            return "int"
        if isinstance(t, ir.IntType) and t.width == 1:
            return "bool"
        if isinstance(t, ir.IntType) and t.width == 32:
            return "int"
        if t == self.f64_ty:
            return "float"
        if t == self.voidptr_ty:
            return "str"
        if isinstance(t, ir.VoidType):
            return "void"
        if isinstance(t, ir.PointerType):
            return "ptr"
        if isinstance(t, ir.ArrayType):
            return "ptr"
        if isinstance(t, ir.LiteralStructType):
            return "ptr"
        if isinstance(t, ir.IdentifiedStructType):
            return "ptr"
        return "unknown"