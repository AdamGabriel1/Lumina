"""Análise semântica de statements."""
from ...ast import (
    VarDecl, DestructureStmt, AssignStmt, ReturnStmt, IfStmt, WhileStmt,
    ForStmt, MatchStmt, ContinueStmt, DeferStmt, BreakStmt, AssertStmt,
    BenchStmt, ErrorNode, MacroCallStmt,
    CompoundAssignStmt,   # NOVO (P-10-2)
)

from .helpers import HelpersMixin
from .var_decl import VarDeclMixin
from .control import ControlMixin
from .match import MatchStmtMixin
from .flow import FlowMixin
from .macro_stmt import MacroStmtMixin


class StatementAnalyzer(
    HelpersMixin,
    VarDeclMixin,
    ControlMixin,
    MatchStmtMixin,
    FlowMixin,
    MacroStmtMixin,
):
    """Dispatcher + mixins de análise de statements."""

    def analyze_stmt(self, node):
        if isinstance(node, ErrorNode):
            return

        if isinstance(node, VarDecl):
            return self._analyze_var_decl(node)

        if isinstance(node, DestructureStmt):
            return self._analyze_destructure(node)

        if isinstance(node, AssignStmt):
            return self._analyze_assign(node)

        # FIX (P-10-2): CompoundAssignStmt tem análise própria para
        # visitar o target uma única vez.
        if isinstance(node, CompoundAssignStmt):
            return self._analyze_compound_assign(node)

        if isinstance(node, ReturnStmt):
            return self._analyze_return(node)

        if isinstance(node, IfStmt):
            return self._analyze_if(node)

        if isinstance(node, WhileStmt):
            return self._analyze_while(node)

        if isinstance(node, ForStmt):
            return self._analyze_for(node)

        if isinstance(node, MatchStmt):
            return self._analyze_match_stmt(node)

        if isinstance(node, ContinueStmt):
            return

        if isinstance(node, BreakStmt):
            return

        if isinstance(node, DeferStmt):
            return self._analyze_defer(node)

        if isinstance(node, AssertStmt):
            return self._analyze_assert(node)

        if isinstance(node, BenchStmt):
            return self._analyze_bench(node)

        if isinstance(node, MacroCallStmt):
            return self._analyze_macro_call_stmt(node)

        return self.visit(node)