"""Validação de macros.

A resolução de métodos default de traits foi movida para o semantic
(`lumina/semantic/trait_resolution.py::TraitResolutionMixin`).

Motivo: existiam duas implementações quase idênticas — uma aqui, outra
no semantic — e elas iam divergir na primeira feature nova de trait.
Como `SemanticAnalyzer.analyze` muta a AST antes do codegen rodar, o
`ImplBlock.methods` já contém os defaults quando
`LLVMCodegen.generate_module` é chamado. Re-resolver aqui era
redundante e arriscado.
"""
from ..errors import LuminaError


class TraitsMixin:

    # ==================================================================
    # Validação de macros
    # ==================================================================
    def _validate_macro(self, fn):
        """Validação mínima de uma macro declarada.

        Uma macro pode ter corpo:
          - `return <expr>`             → usável como expressão (`nome(args)`)
          - múltiplos statements        → usável só em statement (`nome!(args)`)

        Como a mesma macro pode ser usada de duas formas, NÃO validamos
        `return <expr>` aqui — quem decide é o call site:
          - `_expand_macro_expr` exige `return <expr>` quando chamada como
            expressão.
          - `_expand_macro_stmt` aceita qualquer corpo.

        Aqui só garantimos que o corpo não está vazio.
        """
        body = fn.body or []
        if len(body) == 0:
            raise LuminaError(
                f"Macro '{fn.name}' tem corpo vazio.",
                filename="<macro>",
                line=getattr(fn, 'line', 0) or 0,
                col=getattr(fn, 'col', 0) or 0,
                source_code="",
            )