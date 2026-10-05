from .patterns import PatternParser
from ..lexer.tokens import TokenType
from ..ast import (
    VarDecl, DestructureStmt, AssignStmt, ReturnStmt, IfStmt, WhileStmt,
    ForStmt, BreakStmt, ContinueStmt, DeferStmt, AssertStmt, BenchStmt,
    Function, BinaryExpr, MacroCallStmt,
    CompoundAssignStmt,
)


class StatementParser(PatternParser):
    """Statements e estruturas de controle."""

    def parse_statement(self):
        self._skip_newlines_and_comments()

        if (not self.current_token()
                or self.check(TokenType.EOF)
                or self.check(TokenType.DEDENT)):
            self.pending_comments.clear()
            return None

        leading = self._take_comments()
        result = self._parse_statement_inner()

        if result is not None and leading:
            try:
                result.leading_comments = leading
            except AttributeError:
                pass

        return result

    def _parse_statement_inner(self):
        token = self.current_token()
        if not token:
            return None
        if token.type == TokenType.LET or token.type == TokenType.MUT:
            return self.parse_let()
        elif token.type == TokenType.RETURN:
            return self.parse_return()
        elif token.type == TokenType.IF:
            return self.parse_if()
        elif token.type == TokenType.WHILE:
            return self.parse_while()
        elif token.type == TokenType.FOR:
            return self.parse_for()
        elif token.type == TokenType.BREAK:
            self.consume()
            self.match(TokenType.NEWLINE)
            return BreakStmt()
        elif token.type == TokenType.CONTINUE:
            self.consume()
            self.match(TokenType.NEWLINE)
            return ContinueStmt()
        elif token.type == TokenType.IMPORT:
            return self.parse_import()
        elif token.type == TokenType.EXTERN:
            return self.parse_extern()
        elif token.type == TokenType.DEFER:
            return self.parse_defer()
        elif token.type == TokenType.ASSERT:
            return self.parse_assert()
        elif token.type == TokenType.BENCH:
            return self.parse_bench()
        elif token.type == TokenType.TEST:
            return self.parse_test()
        elif token.type == TokenType.MATCH:
            return self.parse_match_stmt()
        elif token.type == TokenType.SWITCH:
            return self.parse_switch()
        elif (token.type == TokenType.IDENT
              and self.peek(1) and self.peek(1).type == TokenType.BANG
              and self.peek(2) and self.peek(2).type == TokenType.LPAREN):
            return self._parse_macro_call_stmt()
        elif (token.type == TokenType.IDENT
              and self.peek(1) and self.peek(1).type == TokenType.COLON_ASSIGN):
            var_token = self.consume()
            self.consume()
            value = self.parse_expression()
            self.match(TokenType.NEWLINE)
            return VarDecl(var_token.value, None, value, True,
                           var_token.line, var_token.col)
        else:
            expr = self.parse_expression()

            if self.check(TokenType.ASSIGN):
                self.consume()
                value = self.parse_expression()
                self.match(TokenType.NEWLINE)
                return AssignStmt(expr, value)

            compound = self._parse_compound_assign(expr)
            if compound is not None:
                self.match(TokenType.NEWLINE)
                return compound

            self.match(TokenType.NEWLINE)
            return expr

    def _parse_macro_call_stmt(self):
        name_token = self.consume()
        self.consume()
        self.consume()
        args = []
        if not self.check(TokenType.RPAREN):
            while True:
                args.append(self.parse_expression())
                if not self.match(TokenType.COMMA):
                    break
        self.expect(TokenType.RPAREN)
        self.match(TokenType.NEWLINE)
        return MacroCallStmt(
            name_token.value, args, name_token.line, name_token.col,
        )

    def _parse_compound_assign(self, target_expr):
        compound_ops = {
            TokenType.PLUS_ASSIGN:  "+",
            TokenType.MINUS_ASSIGN: "-",
            TokenType.STAR_ASSIGN:  "*",
            TokenType.SLASH_ASSIGN: "/",
            TokenType.AMP_ASSIGN:   "&",
            TokenType.PIPE_ASSIGN:  "|",
            TokenType.CARET_ASSIGN: "^",
        }
        tok = self.current_token()
        if not tok or tok.type not in compound_ops:
            return None

        op_token = self.consume()
        value = self.parse_expression()
        return CompoundAssignStmt(target_expr, compound_ops[op_token.type], value)

    def parse_let(self):
        if self.check(TokenType.MUT):
            is_mutable = True
            self.consume()
        else:
            is_mutable = False
            self.expect(TokenType.LET)
        if self.check(TokenType.LPAREN):
            self.consume()
            names = []
            while True:
                if self.check(TokenType.RPAREN):
                    break
                names.append(self.expect(TokenType.IDENT).value)
                if self.match(TokenType.COMMA):
                    continue
                else:
                    break
            self.expect(TokenType.RPAREN)
            self.expect(TokenType.ASSIGN)
            expr = self.parse_expression()
            self.match(TokenType.NEWLINE)
            return DestructureStmt(names, expr, is_mutable)
        var_token = self.expect(TokenType.IDENT)
        var_name = var_token.value
        var_line, var_col = var_token.line, var_token.col
        var_type = None
        if self.match(TokenType.COLON):
            var_type = self.parse_type()
        expr = None
        if self.match(TokenType.ASSIGN):
            expr = self.parse_expression()
        self.match(TokenType.NEWLINE)
        return VarDecl(var_name, var_type, expr, is_mutable, var_line, var_col)

    def parse_return(self):
        self.consume(TokenType.RETURN)
        values = []
        if not self.check(TokenType.NEWLINE) and not self.check(TokenType.DEDENT):
            values.append(self.parse_expression())
            while self.match(TokenType.COMMA):
                values.append(self.parse_expression())
        self.match(TokenType.NEWLINE)
        return ReturnStmt(values)

    def parse_if(self):
        self.consume(TokenType.IF)
        return self._parse_if_core()

    def _parse_block_body(self):
        """Parseia o corpo de um bloco após o `:`.

        Suporta duas formas:
          - Inline:     `: stmt NEWLINE`
          - Multi-linha: `: NEWLINE INDENT stmts... DEDENT`

        Retorna lista de statements. O `:` já foi consumido pelo
        chamador. Espera que `_skip_trailing_comment` já tenha rodado
        (ou roda aqui, é idempotente).
        """
        self._skip_trailing_comment()

        # Corpo inline: statement na mesma linha do `:`
        if not self.check(TokenType.NEWLINE):
            stmt = self.parse_statement()
            return [stmt] if stmt is not None else []

        # Corpo multi-linha
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
        return body

    def _parse_if_core(self):
        condition = self.parse_expression()
        self.expect(TokenType.COLON)
        self._skip_trailing_comment()

        then_body = self._parse_block_body()

        else_body = None
        # Após o then_body, estamos de volta ao nível do `if`.
        # Se houver `elif`/`else` na sequência, são do MESMO if.
        if self.check(TokenType.ELIF):
            self.consume()
            # `elif` é `if` aninhado dentro do `else`.
            else_body = [self._parse_if_core()]
        elif self.check(TokenType.ELSE):
            self.consume()
            self.expect(TokenType.COLON)
            else_body = self._parse_block_body()

        return IfStmt(condition, then_body, else_body)

    def parse_while(self):
        self.consume(TokenType.WHILE)
        condition = self.parse_expression()
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
        return WhileStmt(condition, body)

    # ==================================================================
    # v0.7.0: `for x: T in arr:` — anotação opcional do tipo do elemento.
    #
    # Desambiguação: após o(s) nome(s) da variável, se virmos `:` seguido
    # de `IDENT` (nome de tipo), é anotação. Se virmos `:` seguido de
    # `NEWLINE`, é o marcador de bloco. Como `IN` nunca é uma keyword
    # ambígua aqui, o lookahead é confiável.
    #
    # Sintaxe suportada:
    #   for x in arr:
    #   for i, x in arr:
    #   for x: float in arr:
    #   for i, x: float in arr:
    # ==================================================================
    def parse_for(self):
        self.consume(TokenType.FOR)
        first = self.expect(TokenType.IDENT).value
        second = None
        if self.check(TokenType.COMMA):
            self.consume()
            second = self.expect(TokenType.IDENT).value

        # Anotação opcional `: T` antes do `in`.
        elem_type = None
        if self.check(TokenType.COLON):
            next_tok = self.peek(1)
            if next_tok and next_tok.type == TokenType.IDENT:
                self.consume()   # COLON
                elem_type = self.parse_type()

        self.expect(TokenType.IN)
        start = None
        end = None
        iterable = None
        first_expr = self.parse_additive()
        if self.check(TokenType.DOT_DOT):
            self.consume()
            start = first_expr
            end = self.parse_additive()
        else:
            iterable = first_expr

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

        if second is not None:
            return ForStmt(second, start, end, iterable, body,
                           index_var=first, elem_type=elem_type)
        return ForStmt(first, start, end, iterable, body, elem_type=elem_type)

    def parse_defer(self):
        self.consume(TokenType.DEFER)
        if self.match(TokenType.COLON):
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
            return DeferStmt(body, False)
        expr = self.parse_expression()
        self.match(TokenType.NEWLINE)
        return DeferStmt([expr], False)

    def parse_assert(self):
        self.consume(TokenType.ASSERT)
        self.expect(TokenType.LPAREN)
        cond = self.parse_expression()
        self.expect(TokenType.RPAREN)
        self.match(TokenType.NEWLINE)
        return AssertStmt(cond)

    def parse_test(self):
        self.consume(TokenType.TEST)
        test_name = self.expect(TokenType.STRING).value
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
        return Function(f"test_{test_name.replace(' ', '_')}", [], "int", body)

    def parse_bench(self):
        self.consume(TokenType.BENCH)
        bench_name = self.expect(TokenType.STRING).value
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
        return BenchStmt(bench_name, body)