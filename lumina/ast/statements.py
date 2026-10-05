from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from .expressions import Expr, Param


class Stmt:
    """Classe base para todos os statements."""
    def accept(self, visitor):
        return visitor.visit(self)


# ==========================================
# DECLARAÇÕES DE ESTRUTURAS E TRAITS
# ==========================================
@dataclass
class StructDecl(Stmt):
    name: str
    fields: Dict[str, str]
    type_params: Optional[List[str]] = None
    line: int = 0
    col: int = 0


@dataclass
class EnumDecl(Stmt):
    name: str
    variants: List[tuple]
    type_params: Optional[List[str]] = None
    line: int = 0
    col: int = 0


@dataclass
class TraitDecl(Stmt):
    name: str
    methods: List[Any]
    line: int = 0
    col: int = 0


@dataclass
class ImplBlock(Stmt):
    struct_name: str
    methods: List[Any]
    trait_name: Optional[str] = None
    line: int = 0
    col: int = 0


# ==========================================
# DECLARAÇÕES DE VARIÁVEIS E FUNÇÕES
# ==========================================
@dataclass
class VarDecl(Stmt):
    name: str
    var_type: Optional[str]
    value: Optional[Expr]
    is_mutable: bool
    line: int = 0
    col: int = 0


@dataclass
class DestructureStmt(Stmt):
    names: List[str]
    value: Expr
    is_mutable: bool


@dataclass
class Function(Stmt):
    name: str
    params: List[Param]
    return_type: str
    body: List[Any]
    type_params: Optional[List[str]] = None
    line: int = 0
    col: int = 0
    is_exported: bool = False
    attrs: Optional[List[str]] = None


@dataclass
class ExternDecl(Stmt):
    name: str
    params: List[tuple]
    return_type: str
    is_wasm: bool = False
    line: int = 0
    col: int = 0


@dataclass
class ImportStmt(Stmt):
    filename: str
    line: int = 0
    col: int = 0


# ==========================================
# CONTROLE DE FLUXO
# ==========================================
@dataclass
class AssignStmt(Stmt):
    target: Expr
    value: Expr


@dataclass
class CompoundAssignStmt(Stmt):
    target: Expr
    op: str          # '+', '-', '*', '/', '&', '|', '^'
    value: Expr


@dataclass
class ReturnStmt(Stmt):
    values: List[Expr]
    line: int = 0
    col: int = 0


@dataclass
class IfStmt(Stmt):
    condition: Expr
    then_body: List[Any]
    else_body: Optional[List[Any]] = None


@dataclass
class WhileStmt(Stmt):
    condition: Expr
    body: List[Any]


# v0.7.0: `elem_type` — anotação opcional do tipo do elemento
# para iterar sobre `ptr` sem perder tipo.
#
#     for x: float in arr:    # arr é `ptr`, mas iteramos f64
#         print(x)
#
# Sem a anotação, `for x in arr` mantém o comportamento anterior
# (element type = tipo de `ptr.pointee`, tipicamente i64).
#
# A anotação é validada no semantic contra o LLVM type do array;
# se incompatível (ex: `f64` em array de `str`), o bitcast gerado
# reinterpeta os bits — é responsabilidade do usuário.
@dataclass
class ForStmt(Stmt):
    var_name: str
    start: Optional[Expr]
    end: Optional[Expr]
    iterable: Optional[Expr]
    body: List[Any]
    index_var: Optional[str] = None
    elem_type: Optional[str] = None   # v0.7.0


@dataclass
class MatchStmt(Stmt):
    condition: Expr
    cases: List[tuple]
    default: Optional[List[Any]] = None


# ==========================================
# UTILITÁRIOS E TESTES
# ==========================================
@dataclass
class BreakStmt(Stmt):
    pass


@dataclass
class ContinueStmt(Stmt):
    pass


@dataclass
class DeferStmt(Stmt):
    body: List[Any]
    is_errdefer: bool = False


@dataclass
class AssertStmt(Stmt):
    condition: Expr


@dataclass
class BenchStmt(Stmt):
    name: str
    body: List[Any]


@dataclass
class ErrorNode(Stmt):
    message: str
    line: int = 0
    col: int = 0


@dataclass
class MacroCallStmt(Stmt):
    name: str
    args: List[Expr]
    line: int = 0
    col: int = 0


@dataclass
class TypeAlias(Stmt):
    name: str
    target_type: str
    type_params: Optional[List[str]] = None
    line: int = 0
    col: int = 0