"""Resolução de métodos default de traits.

Passos:
  1. Registra aliases `metodo` → `Struct_metodo` para chamadas de trait.
  2. Copia métodos default do trait para cada `ImplBlock` que não os
     sobrescreveu.
  3. Detecta conflito: dois ImplBlocks produzindo o mesmo
     `Struct_metodo`. Sem este guard, o segundo silenciosamente
     sobrescreveria o primeiro em `function_defs`.
"""
from ..ast import Function, Param, ImplBlock, TraitDecl
from ..common.mangle import mangle_method, mangle_type
from ..errors import LuminaError


class TraitResolutionMixin:

    def _resolve_trait_defaults(self, declarations):
        traits_by_name = {}
        for decl in declarations:
            if isinstance(decl, TraitDecl):
                traits_by_name[decl.name] = decl

        # Passo 1: registra aliases `metodo` → `Struct_metodo`.
        for decl in declarations:
            if not isinstance(decl, ImplBlock):
                continue
            trait_name = getattr(decl, 'trait_name', None)
            if not trait_name or trait_name not in traits_by_name:
                continue
            trait_def = traits_by_name[trait_name]
            for trait_method in trait_def.methods:
                full_name = mangle_method(decl.struct_name, trait_method.name)
                if full_name not in self.functions:
                    self.functions.add(full_name)
                self.functions.add(trait_method.name)
                if trait_method.name not in self.function_defs:
                    self.function_defs[trait_method.name] = Function(
                        trait_method.name, [], trait_method.return_type, [],
                    )

        # Passo 2: copia métodos default para o ImplBlock que não os sobrescreve.
        for decl in declarations:
            if not isinstance(decl, ImplBlock):
                continue
            trait_name = getattr(decl, 'trait_name', None)
            if not trait_name or trait_name not in traits_by_name:
                continue

            trait_def = traits_by_name[trait_name]
            explicit_names = {m.name for m in decl.methods}

            for trait_method in trait_def.methods:
                full_name = mangle_method(decl.struct_name, trait_method.name)
                if full_name in explicit_names:
                    continue
                if not trait_method.body:
                    continue

                default_method = Function(
                    full_name,
                    [Param('self', decl.struct_name)] + list(trait_method.params),
                    trait_method.return_type,
                    list(trait_method.body),
                )
                decl.methods.append(default_method)

        # Passo 3: guard de duplicata.
        #
        # FIX 12: mensagem mais acionável, distinguindo trait-default
        # de impl explícito. Caso real:
        #
        #   trait Greet:
        #       fn hello() -> int: return 1
        #   struct S: x: int
        #   impl Greet for S: pass        # gera S_hello default
        #   impl S:
        #       fn hello() -> int: return 2
        #
        # Sem o guard, `S_hello` seria definido duas vezes e o segundo
        # silenciosamente sobrescreveria o primeiro.
        seen_methods = {}  # mangled_name → (struct_name, trait_name_or_None)
        for decl in declarations:
            if not isinstance(decl, ImplBlock):
                continue
            trait_name = getattr(decl, 'trait_name', None)
            for m in decl.methods:
                key = m.name
                if key in seen_methods:
                    prev_struct, prev_trait = seen_methods[key]
                    prev_desc = (
                        f"impl {prev_trait} for {prev_struct}"
                        if prev_trait else f"impl {prev_struct}"
                    )
                    curr_desc = (
                        f"impl {trait_name} for {decl.struct_name}"
                        if trait_name else f"impl {decl.struct_name}"
                    )

                    # Hint específico quando um lado é trait-default e o
                    # outro é impl explícito.
                    hint = ""
                    if (prev_trait is None) != (trait_name is None):
                        hint = (
                            " Um dos métodos vem de trait default e o outro "
                            "de um impl explícito. Se o impl explícito é "
                            "intencional, declare o método explicitamente "
                            "no outro impl também para desambiguar."
                        )

                    raise LuminaError(
                        message=(
                            f"Método duplicado '{key}': definido em "
                            f"'{prev_desc}' e novamente em '{curr_desc}'."
                            f"{hint}"
                        ),
                        filename=getattr(decl, 'filename', '<semantic>'),
                        line=getattr(m, 'line', 0) or 0,
                        col=getattr(m, 'col', 0) or 0,
                        source_code=getattr(self, 'source_code', '') or '',
                    )
                seen_methods[key] = (decl.struct_name, trait_name)