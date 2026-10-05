from ..lexer.tokens import TokenType, KEYWORDS
from ..errors import LuminaError


class ParserBase:
    """Primitivas de consumo de tokens."""

    def __init__(self, tokens, filename="program.lm", source_code=""):
        self.tokens = tokens
        self.pos = 0
        self.filename = filename
        self.source_code = source_code
        self.no_struct_literal = False
        self.pending_comments = []
        # ADR 0003 — profundidade de `quote:` aberto no parser.
        # > 0 significa que `~` é unquote (não bitwise NOT).
        self._in_quote_depth = 0

    def current_token(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def peek(self, offset=1):
        if self.pos + offset < len(self.tokens):
            return self.tokens[self.pos + offset]
        return None

    def consume(self, expected_type=None):
        token = self.current_token()
        if token and (expected_type is None or token.type == expected_type):
            self.pos += 1
            return token
        if token:
            err = LuminaError(
                f"Esperado {expected_type.name if expected_type else 'token'}, mas encontrei {token.type.name} ('{token.value}')",
                filename=self.filename, line=token.line, col=token.col, source_code=self.source_code,
            )
            if expected_type in KEYWORDS.values():
                expected_word = next((k for k, v in KEYWORDS.items() if v == expected_type), None)
                if expected_word:
                    err.add_note(f"Você quis dizer '{expected_word}'?")
            raise err
        raise LuminaError(
            "Fim inesperado do código",
            filename=self.filename, line=0, col=0, source_code=self.source_code,
        )

    def check(self, t_type: TokenType, t_val: str = None) -> bool:
        t = self.current_token()
        if not t:
            return False
        if t.type != t_type:
            return False
        if t_val is not None and t.value != t_val:
            return False
        return True

    def match(self, t_type: TokenType, t_val: str = None) -> bool:
        if t_type == TokenType.NEWLINE:
            self._skip_trailing_comment()
        if t_type == TokenType.INDENT:
            self._skip_newlines_and_comments()
        if self.check(t_type, t_val):
            self.consume()
            return True
        return False

    def expect(self, t_type: TokenType, t_val: str = None):
        if t_type == TokenType.NEWLINE:
            self._skip_trailing_comment()
        if t_type == TokenType.INDENT:
            self._skip_newlines_and_comments()
        if self.check(t_type, t_val):
            return self.consume()
            
        t = self.current_token()
        expected = f"{t_type.name}" + (f" ('{t_val}')" if t_val else "")
        found = f"{t.type.name} ('{t.value}')" if t else "EOF"
        
        err = LuminaError(
            f"Esperado {expected}, mas encontrei {found}",
            filename=self.filename, line=t.line if t else 0,
            col=t.col if t else 0, source_code=self.source_code,
        )
        
        # Correção: usar t_type em vez de expected_type
        if t and t_type in KEYWORDS.values():
            expected_word = next((k for k, v in KEYWORDS.items() if v == t_type), None)
            if expected_word:
                err.add_note(f"Você quis dizer '{expected_word}'?")
                
        raise err

    def _skip_trailing_comment(self):
        if (self.current_token() and self.current_token().type == TokenType.COMMENT):
            next_t = self.peek(1)
            if next_t and next_t.type == TokenType.NEWLINE:
                self.pending_comments.append(self.current_token().value)
                self.consume()

    def _skip_comments(self):
        while self.current_token() and self.current_token().type == TokenType.COMMENT:
            self.pending_comments.append(self.current_token().value)
            self.consume()

    def _skip_newlines_and_comments(self):
        while self.current_token() and (self.check(TokenType.NEWLINE) or self.check(TokenType.COMMENT)):
            if self.check(TokenType.COMMENT):
                self.pending_comments.append(self.current_token().value)
            self.consume()

    def _take_comments(self):
        result = list(self.pending_comments)
        self.pending_comments.clear()
        return result