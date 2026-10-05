from llvmlite import ir
from ..common.mangle import mangle_type, mangle_slice
from ..errors import LuminaError
from ..semantic.types import substitute_generic, _is_slice_type, _slice_inner


class TypesCodegen:

    # ==================================================================
    # v0.8.0: `[T]` — slice type.
    # Representação: `%Slice_T_` = `{T*, i64}`.
    # Passado por ponteiro em params (como toda struct Lumina).
    # ==================================================================
    def get_or_create_slice_type(self, type_name):
        """type_name: `'[T]'`. Retorna `%Slice_T_*`."""

        if type_name in self.struct_types:
            return self.struct_types[type_name]

        inner = _slice_inner(type_name)
        mangled = mangle_slice(inner)

        slice_ty = self.module.context.get_identified_type(mangled)
        self.struct_types[type_name] = slice_ty
        self.struct_types[mangled] = slice_ty

        # Corpo: {T*, i64}
        inner_llvm_ty = self.get_llvm_type(inner)

        # Se o elemento é uma struct identificada, o campo é `%T*`.
        # Se é `T*` já (pointer), o campo é `T**`.
        # Na prática, arrays de structs guardam `%T*` no slot,
        # então o campo do slice é `%T**`.
        if isinstance(inner_llvm_ty, ir.IdentifiedStructType):
            field_ty = inner_llvm_ty.as_pointer()
        else:
            field_ty = inner_llvm_ty.as_pointer()

        slice_ty.set_body(field_ty, self.i64_ty)

        fields_map = {"data": 0, "len": 1}
        self.struct_fields[type_name] = fields_map
        self.struct_fields[mangled] = fields_map
        # Registra um def stub — não é usado como struct normal,
        # mas garante que lookups de `struct_defs` não explodem.
        self.struct_defs.setdefault(type_name, _SliceTypeDecl(type_name))

        return slice_ty

    def get_llvm_type(self, type_name):
        if type_name == "int":
            return self.i64_ty
        elif type_name == "float":
            return self.f64_ty
        elif type_name == "str":
            return self.voidptr_ty
        elif type_name == "ptr":
            return self.i64_ty.as_pointer()
        elif type_name == "fn" or type_name.startswith("fn("):
            return self.voidptr_ty
        elif type_name == "bool":
            return ir.IntType(1)
        elif type_name == "void":
            return ir.VoidType()
        elif _is_slice_type(type_name):
            return self.get_or_create_slice_type(type_name)
        elif type_name in self.struct_types:
            return self.struct_types[type_name]

        # ----------------------------------------------------------
        # FIX — registro on-demand de structs/enums não-genéricos.
        #
        # Antes, uma struct `A` que referencia `B` declarada depois
        # (tipicamente via import resolvido depois no AST) tinha o
        # campo tipado como `i64` por causa do fallback silencioso
        # abaixo. O bug se manifestava como leitura de membro
        # retornando 0 (o codegen pensava que era primitivo).
        #
        # Agora, se a struct está em `struct_defs` mas ainda não foi
        # registrada, registramos na hora. Isso funciona para
        # referências não-cíclicas (`A` usa `B` que ainda não foi
        # vista) e também para ciclos, porque `register_struct` já
        # coloca o tipo em `struct_types` **antes** de processar os
        # campos (então uma autoreferência recursiva encontra o tipo
        # já registrado e não entra em loop).
        # ----------------------------------------------------------
        if type_name in self.struct_defs:
            decl = self.struct_defs[type_name]
            type_params = getattr(decl, 'type_params', None)
            if not type_params:
                if hasattr(decl, 'variants'):
                    self.register_enum(decl)
                    return self.struct_types[type_name]
                if hasattr(decl, 'fields'):
                    self.register_struct(decl)
                    return self.struct_types[type_name]

        if type_name in self.struct_defs and getattr(
            self.struct_defs[type_name], 'type_params', None
        ):
            base_decl = self.struct_defs[type_name]
            default_args = ["int"] * len(base_decl.type_params)
            full = f"{type_name}<{','.join(default_args)}>"
            if hasattr(base_decl, 'variants'):
                return self.get_or_create_monomorphized_enum(full)
            return self.get_or_create_monomorphized_struct(full)
        elif "<" in type_name:
            base = type_name.split("<")[0]
            if base in self.struct_defs and hasattr(self.struct_defs[base], 'variants'):
                return self.get_or_create_monomorphized_enum(type_name)
            return self.get_or_create_monomorphized_struct(type_name)
        return self.i64_ty

    def get_llvm_param_type(self, type_name):
        llvm_ty = self.get_llvm_type(type_name)
        if isinstance(llvm_ty, ir.IdentifiedStructType):
            return llvm_ty.as_pointer()
        return llvm_ty

    def get_llvm_field_type(self, type_name):
        if type_name in self.struct_types:
            return self.struct_types[type_name].as_pointer()
        return self.get_llvm_type(type_name)

    def get_or_create_monomorphized_struct(self, type_name):
        if type_name in self.struct_types:
            return self.struct_types[type_name]

        base_name, _, args_str = type_name.partition('<')
        args_str = args_str.rstrip('>')
        type_args = [a.strip() for a in args_str.split(',')]

        if base_name not in self.struct_defs:
            raise LuminaError(
                message=f"Struct base '{base_name}' não encontrada.",
                filename=getattr(self, 'current_filename', '<codegen>'),
                line=0, col=0, source_code='',
            )
        base_decl = self.struct_defs[base_name]
        if not base_decl.type_params:
            raise LuminaError(
                message=f"Struct '{base_name}' não é Genérica.",
                filename=getattr(self, 'current_filename', '<codegen>'),
                line=0, col=0, source_code='',
            )

        type_map = dict(zip(base_decl.type_params, type_args))
        mangled = type_name.replace('<', '_').replace('>', '_').replace(',', '_')
        new_ty = self.module.context.get_identified_type(mangled)

        self.struct_types[type_name] = new_ty
        self.struct_types[mangled] = new_ty

        field_tys = [self.get_llvm_type(type_map.get(ft, ft)) for ft in base_decl.fields.values()]
        new_ty.set_body(*field_tys)

        fields_map = {name: i for i, name in enumerate(base_decl.fields.keys())}
        self.struct_fields[type_name] = fields_map
        self.struct_fields[mangled] = fields_map
        self.struct_defs[type_name] = base_decl
        self.struct_defs[mangled] = base_decl

        return new_ty

    def get_or_create_monomorphized_enum(self, type_name):
        if type_name in self.struct_types:
            return self.struct_types[type_name]

        base_name, _, args_str = type_name.partition('<')
        args_str = args_str.rstrip('>')
        type_args = [a.strip() for a in args_str.split(',')]

        if base_name not in self.struct_defs:
            raise LuminaError(
                message=f"Enum base '{base_name}' não encontrado.",
                filename=getattr(self, 'current_filename', '<codegen>'),
                line=0, col=0, source_code='',
            )
        base_decl = self.struct_defs[base_name]
        if not getattr(base_decl, 'type_params', None):
            raise LuminaError(
                message=f"Enum '{base_name}' não é genérico.",
                filename=getattr(self, 'current_filename', '<codegen>'),
                line=0, col=0, source_code='',
            )

        type_map = dict(zip(base_decl.type_params, type_args))
        mangled = mangle_type(type_name)
        new_ty = self.module.context.get_identified_type(mangled)

        self.struct_types[type_name] = new_ty
        self.struct_types[mangled] = new_ty

        max_p = self._enum_max_payloads(base_decl)
        fields = [ir.IntType(32)]
        for i in range(max_p):
            payload_ty = ir.IntType(64)
            for v in base_decl.variants:
                v_payloads = v[1] if len(v) > 1 else []
                if isinstance(v_payloads, list) and i < len(v_payloads):
                    concrete = substitute_generic(v_payloads[i], type_map)
                    payload_ty = self.get_llvm_type(concrete)
                    break
            fields.append(payload_ty)

        new_ty.set_body(*fields)

        fields_map = {"tag": 0}
        for i in range(max_p):
            fields_map[f"payload_{i}"] = i + 1
        if max_p >= 1:
            fields_map["payload"] = 1
        self.struct_fields[type_name] = fields_map
        self.struct_fields[mangled] = fields_map
        self.struct_defs[type_name] = base_decl
        self.struct_defs[mangled] = base_decl

        if hasattr(self, '_invalidate_variant_cache'):
            self._invalidate_variant_cache()

        return new_ty


class _SliceTypeDecl:
    """Stub usado por `struct_defs['[T]']` para que lookups de
    `hasattr(decl, 'variants')` e `hasattr(decl, 'fields')` não
    explodam."""
    def __init__(self, name):
        self.name = name
        self.fields = {"data": "ptr", "len": "int"}
        self.type_params = None