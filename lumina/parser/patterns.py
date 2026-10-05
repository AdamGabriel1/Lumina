from .expressions import ExpressionParser
from ..lexer.tokens import TokenType
from ..ast import (
    MatchExpr, MatchStmt, VariableExpr, NumberExpr, StringExpr,
    StructLiteralExpr, StructLiteralField,
)
from ..errors import LuminaError


class PatternParser(ExpressionParser):

    # ==================================================================
    # Helpers compartilhados
    # ==================================================================
    def _parse_case_body(self):
        """Parseia o corpo de um `case`/`default`.

        FIX (Fase 10b / P-10-3): se após o `:\n` não houver INDENT,
        retorna `[]` (corpo vazio). Antes, `expect(INDENT)` falhava
        mesmo quando o próximo token era um `case` (fallthrough) ou
        `default`.
        """
        if self.check(TokenType.NEWLINE):
            self.expect(TokenType.NEWLINE)
            while self.check(TokenType.NEWLINE):
                self.consume()
            # Corpo vazio — sem INDENT. Deixa o caller decidir (pode
            # ser fallthrough para o próximo case, ou corpo vazio
            # legítimo).
            if not self.check(TokenType.INDENT):
                return []
            self.expect(TokenType.INDENT)
            body = []
            while not self.check(TokenType.DEDENT) and not self.check(TokenType.EOF):
                if self.match(TokenType.NEWLINE):
                    continue
                stmt = self.parse_statement()
                if stmt is not None:
                    body.append(stmt)
            self.expect(TokenType.DEDENT)
            return body

        stmt = self.parse_statement()
        return [stmt] if stmt is not None else []

    def _parse_case_clause(self):
        """Parseia `case <pattern>:` seguido do corpo.

        FIX (Fase 10b / P-10-3): se o corpo for vazio e o próximo
        token for `case`, mescla os patterns:

            case 1:
            case 2:
                print(42)

        vira internamente `case 1 | 2: print(42)`.

        Guards e bindings são rejeitados quando há merge — não fazem
        sentido com múltiplos patterns.
        """
        self.consume(TokenType.CASE)
        variant, bindings, guard = self._parse_case_pattern()
        self.expect(TokenType.COLON)
        body = self._parse_case_body()

        # Fallthrough: enquanto o corpo for vazio e vier outro `case`,
        # mescla o pattern.
        while not body and self.check(TokenType.CASE):
            if bindings is not None:
                t = self.current_token()
                raise LuminaError(
                    "Case com binding ('case x:') não pode ter corpo vazio — "
                    "o binding não estaria associado a nenhum corpo. "
                    "Se quer fallthrough, use patterns literais.",
                    self.filename, t.line, t.col, self.source_code,
                )

            self.consume(TokenType.CASE)
            next_variant, next_bindings, next_guard = self._parse_case_pattern()
            self.expect(TokenType.COLON)

            if next_guard is not None:
                t = self.current_token()
                raise LuminaError(
                    "Guard ('if ...') não pode ser combinado com case de corpo "
                    "vazio — o pattern do case seguinte seria mesclado.",
                    self.filename, t.line, t.col, self.source_code,
                )
            if next_bindings is not None:
                t = self.current_token()
                raise LuminaError(
                    "Binding no case seguinte não pode ser combinado com "
                    "case de corpo vazio.",
                    self.filename, t.line, t.col, self.source_code,
                )

            # Mescla os patterns.
            if isinstance(variant, list):
                if isinstance(next_variant, list):
                    variant = variant + next_variant
                else:
                    variant = variant + [next_variant]
            else:
                if isinstance(next_variant, list):
                    variant = [variant] + next_variant
                else:
                    variant = [variant, next_variant]

            body = self._parse_case_body()

        return (variant, bindings, guard, body)

    def _parse_default_clause(self):
        self.consume(TokenType.DEFAULT)
        self.expect(TokenType.COLON)
        return self._parse_case_body()

    def _parse_cases_block(self):
        cases = []
        default = None
        while not self.check(TokenType.DEDENT) and not self.check(TokenType.EOF):
            if self.match(TokenType.NEWLINE):
                continue
            if self.check(TokenType.CASE):
                cases.append(self._parse_case_clause())
            elif self.check(TokenType.DEFAULT):
                default = self._parse_default_clause()
            else:
                t = self.current_token()
                raise LuminaError(
                    f"Esperado 'case' ou 'default' dentro de 'match', "
                    f"mas encontrei {t.type.name} ('{t.value}')",
                    filename=self.filename, line=t.line, col=t.col,
                    source_code=self.source_code,
                )
        self.expect(TokenType.DEDENT)
        return cases, default

    def _parse_case_pattern(self):
        variants = [self._parse_single_pattern()]

        while self.check(TokenType.PIPE):
            next_tok = self.peek(1)
            if next_tok and next_tok.type == TokenType.GT:
                break
            self.consume()
            variants.append(self._parse_single_pattern())

        bindings = None
        for i, v in enumerate(variants):
            if isinstance(v, tuple):
                variant_val, variant_binding = v
                variants[i] = variant_val
                if variant_binding is not None:
                    if bindings is not None or len(variants) > 1:
                        t = self.current_token()
                        raise LuminaError(
                            "Multi-pattern com binding não é suportado. Use cases separados.",
                            self.filename, t.line, t.col, self.source_code,
                        )
                    bindings = variant_binding

        if (len(variants) == 1
                and isinstance(variants[0], str)
                and variants[0] not in ("_",)):
            try:
                int(variants[0])
            except (ValueError, TypeError):
                if self.check(TokenType.IF) and bindings is None:
                    bindings = [variants[0]]
                    variants = [None]

        if len(variants) == 1 and variants[0] == "_":
            variants = [None]

        guard = None
        if self.check(TokenType.IF):
            self.consume()
            guard = self.parse_expression()

        variant = variants[0] if len(variants) == 1 else variants
        return variant, bindings, guard

    def _parse_single_pattern(self):
        if self.check(TokenType.NUMBER):
            return self.consume().value, None

        if self.check(TokenType.STRING):
            return StringExpr(self.consume().value), None

        if self.check(TokenType.IDENT):
            name = self.expect(TokenType.IDENT).value
            if name == "_":
                return None, None

            if self.check(TokenType.LBRACE):
                self.consume()
                fields = []
                struct_bindings = []
                while not self.check(TokenType.RBRACE):
                    fname = self.expect(TokenType.IDENT).value
                    if self.check(TokenType.COLON):
                        self.consume()
                        val = self.parse_expression()
                        fields.append(StructLiteralField(fname, val))
                        if isinstance(val, VariableExpr):
                            struct_bindings.append(val.name)
                    else:
                        fields.append(StructLiteralField(fname, VariableExpr(fname, 0, 0)))
                        struct_bindings.append(fname)
                    if not self.match(TokenType.COMMA):
                        break
                self.expect(TokenType.RBRACE)
                return StructLiteralExpr(name, fields), struct_bindings

            if self.check(TokenType.LPAREN):
                self.consume()
                bindings = []
                while True:
                    bindings.append(self.expect(TokenType.IDENT).value)
                    if not self.match(TokenType.COMMA):
                        break
                self.expect(TokenType.RPAREN)
                return name, bindings
            return name, None

        t = self.current_token()
        raise LuminaError(
            f"Esperado NUMBER, STRING ou IDENT após 'case', mas encontrei "
            f"{t.type.name} ('{t.value}')",
            filename=self.filename, line=t.line, col=t.col,
            source_code=self.source_code,
        )

    def parse_match_expr(self):
        self.consume(TokenType.MATCH)
        self.no_struct_literal = True
        cond = self.parse_expression()
        self.no_struct_literal = False

        if self.check(TokenType.COLON):
            self.consume()
            self.expect(TokenType.NEWLINE)
            while self.check(TokenType.NEWLINE):
                self.consume()
            self.expect(TokenType.INDENT)
        else:
            self.expect(TokenType.LBRACE)

        cases = []
        default = None
        while (not self.check(TokenType.DEDENT)
               and not self.check(TokenType.RBRACE)
               and not self.check(TokenType.EOF)):
            if self.match(TokenType.NEWLINE):
                continue

            if self.check(TokenType.CASE):
                self.consume()
                variant, bindings, guard = self._parse_case_pattern()
                self.expect(TokenType.COLON)
                self.expect(TokenType.NEWLINE)
                while self.check(TokenType.NEWLINE):
                    self.consume()
                self.expect(TokenType.INDENT)
                body = []
                while not self.check(TokenType.DEDENT) and not self.check(TokenType.EOF):
                    if self.match(TokenType.NEWLINE):
                        continue
                    stmt = self.parse_statement()
                    if stmt is not None:
                        body.append(stmt)
                self.expect(TokenType.DEDENT)
                binding = (bindings[0]
                           if isinstance(bindings, list) and bindings
                           else bindings)
                if isinstance(variant, StringExpr):
                    variant_name = variant.value
                else:
                    variant_name = variant or binding or "_"
                cases.append((
                    VariableExpr(variant_name, 0, 0),
                    body[0] if body else NumberExpr("0", False),
                ))
            elif self.check(TokenType.ELSE):
                self.consume()
                self.expect(TokenType.FAT_ARROW)
                default = self.parse_expression()
                self.match(TokenType.COMMA)
            else:
                val = self.parse_expression()
                self.expect(TokenType.FAT_ARROW)
                res = self.parse_expression()
                cases.append((val, res))
                self.match(TokenType.COMMA)

        if self.check(TokenType.DEDENT):
            self.consume(TokenType.DEDENT)
        elif self.check(TokenType.RBRACE):
            self.consume(TokenType.RBRACE)
        return MatchExpr(cond, cases, default)

    def parse_match_stmt(self):
        saved_pos = self.pos
        self.consume(TokenType.MATCH)
        self.no_struct_literal = True
        cond = self.parse_expression()
        self.no_struct_literal = False

        is_match_stmt_syntax = False
        if self.check(TokenType.COLON):
            self.consume()
            self.expect(TokenType.NEWLINE)
            while self.check(TokenType.NEWLINE):
                self.consume()
            if self.check(TokenType.INDENT):
                self.consume()
                if self.check(TokenType.CASE) or self.check(TokenType.DEFAULT):
                    is_match_stmt_syntax = True

        if is_match_stmt_syntax:
            cases, default = self._parse_cases_block()
            return MatchStmt(cond, cases, default)

        self.pos = saved_pos
        return self.parse_match_expr()

    def parse_switch(self):
        self.consume(TokenType.SWITCH)
        self.no_struct_literal = True
        cond = self.parse_expression()
        self.no_struct_literal = False

        self.expect(TokenType.COLON)
        self.expect(TokenType.NEWLINE)
        while self.check(TokenType.NEWLINE):
            self.consume()
        self.expect(TokenType.INDENT)

        cases, default = self._parse_cases_block()
        return MatchStmt(cond, cases, default)