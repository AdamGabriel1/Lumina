from .declarations import DeclarationParser
from ..lexer.tokens import TokenType
from ..errors import LuminaError


class Parser(DeclarationParser):
    """Orquestrador — combina todos os mixins via MRO.

    A cadeia de herança é:
      DeclarationParser → StatementParser → PatternParser → ExpressionParser → ParserBase

    Cada camada só depende da anterior (e é chamada de cima pra baixo), então
    não há dependência circular.
    """

    def parse(self):
        declarations = []
        while self.current_token() and not self.check(TokenType.EOF):
            # Consome NEWLINEs e COMMENTs, guardando os comentários.
            self._skip_newlines_and_comments()

            if not self.current_token() or self.check(TokenType.EOF):
                break

            leading = self._take_comments()

            # NOVO: lê atributos `@nome` ou `@nome(arg1, arg2, ...)`
            # antes de decidir qual declaração é.
            attrs = []
            while self.check(TokenType.AT):
                self.consume()
                attr_name = self.expect(TokenType.IDENT).value
                attr_args = []
                if self.match(TokenType.LPAREN):
                    if not self.check(TokenType.RPAREN):
                        while True:
                            attr_args.append(self.expect(TokenType.IDENT).value)
                            if not self.match(TokenType.COMMA):
                                break
                    self.expect(TokenType.RPAREN)
                attrs.append((attr_name, attr_args))

                # NOVO: após cada `@attr(...)`, pode haver NEWLINE(s) antes
                # da próxima declaração (ex: `@derive(Eq)\nstruct Ponto:`).
                self._skip_newlines_and_comments()

            # Guarda para o próximo `parse_*` consumir (parse_function
            # e parse_struct leem `self._pending_attrs`).
            self._pending_attrs = attrs

            is_export = False
            if self.check(TokenType.EXPORT):
                is_export = True
                self.consume()

            decl = None
            if self.check(TokenType.FN):
                decl = self.parse_function()
            elif self.check(TokenType.STRUCT):
                decl = self.parse_struct()
            elif self.check(TokenType.ENUM):
                decl = self.parse_enum()
            elif self.check(TokenType.IMPL):
                decl = self.parse_impl()
            elif self.check(TokenType.TRAIT):
                decl = self.parse_trait()
            elif self.check(TokenType.LET) or self.check(TokenType.MUT) or \
                 self.check(TokenType.CONST) or \
                 self.check(TokenType.TEST) or self.check(TokenType.BENCH) or \
                 self.check(TokenType.IMPORT) or self.check(TokenType.EXTERN):
                decl = self.parse_statement()
            elif self.check(TokenType.TYPE):
                decl = self.parse_type_alias()
            else:
                t = self.current_token()
                raise LuminaError(
                    f"Declaração de nível superior inválida: {t.type.name} ('{t.value}')",
                    filename=self.filename, line=t.line, col=t.col, source_code=self.source_code,
                )

            self._pending_attrs = []

            if is_export and hasattr(decl, 'is_exported'):
                decl.is_exported = True

            if leading and decl is not None:
                try:
                    decl.leading_comments = leading
                except AttributeError:
                    pass

            declarations.append(decl)

        return declarations