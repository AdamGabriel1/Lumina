"""`comptime` — constant folding em tempo de compilação."""
from ...ast import (
    NumberExpr, BoolExpr, StringExpr, BinaryExpr, UnaryExpr, ComptimeExpr,
)
from ...errors import LuminaError


class ComptimeMixin:

    def visit_ComptimeExpr(self, node):
        folded = self._constant_fold(node.expr)
        if folded is None:
            raise LuminaError(
                "`comptime` requer uma expressão constante "
                "(apenas literais e operações aritméticas são suportados por "
                "enquanto).",
                self.filename, getattr(node, 'line', 0),
                getattr(node, 'col', 0), self.source_code,
            )
        node.folded = folded
        return self.visit(folded)

    def _constant_fold(self, node):
        """Tenta avaliar `node` em tempo de compilação.

        Retorna um nó literal (NumberExpr/BoolExpr/StringExpr) ou None.
        Cobre: literais, +, -, *, /, %, unário -, e recursão em ComptimeExpr.
        """
        if isinstance(node, (NumberExpr, BoolExpr, StringExpr)):
            return node

        if isinstance(node, ComptimeExpr):
            return self._constant_fold(node.expr)

        if isinstance(node, BinaryExpr):
            left = self._constant_fold(node.left)
            right = self._constant_fold(node.right)
            if left is None or right is None:
                return None
            if not (isinstance(left, NumberExpr)
                    and isinstance(right, NumberExpr)):
                return None

            try:
                lv = float(left.value) if left.is_float else int(left.value, 0)
                rv = float(right.value) if right.is_float else int(right.value, 0)
            except (ValueError, TypeError):
                return None

            # Comparações
            if node.op == '==':
                return BoolExpr(lv == rv)
            if node.op == '!=':
                return BoolExpr(lv != rv)
            if node.op == '<':
                return BoolExpr(lv < rv)
            if node.op == '>':
                return BoolExpr(lv > rv)
            if node.op == '<=':
                return BoolExpr(lv <= rv)
            if node.op == '>=':
                return BoolExpr(lv >= rv)

            is_float = left.is_float or right.is_float
            try:
                if node.op == '+':
                    result = lv + rv
                elif node.op == '-':
                    result = lv - rv
                elif node.op == '*':
                    result = lv * rv
                elif node.op == '/':
                    if rv == 0:
                        return None
                    result = lv / rv
                    is_float = True
                elif node.op == '%':
                    if rv == 0 or is_float:
                        return None
                    result = lv % rv
                else:
                    return None
            except Exception:
                return None

            if is_float:
                return NumberExpr(repr(float(result)), is_float=True)
            return NumberExpr(str(int(result)), is_float=False)

        if isinstance(node, UnaryExpr):
            val = self._constant_fold(node.val)
            if isinstance(val, NumberExpr):
                if node.op == '-':
                    v = float(val.value) if val.is_float else int(val.value, 0)
                    return NumberExpr(
                        repr(-v) if val.is_float else str(-v),
                        is_float=val.is_float,
                    )
                if node.op == 'not' and isinstance(val, BoolExpr):
                    return BoolExpr(not val.value)
            return None

        return None
