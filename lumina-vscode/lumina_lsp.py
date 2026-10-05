"""LSP Server para a linguagem Lumina.

Implementa o subconjunto de LSP necessário para o VS Code:
  - textDocument/completion
  - textDocument/hover
  - textDocument/definition
  - textDocument/references
  - textDocument/prepareRename + textDocument/rename
  - textDocument/documentSymbol
  - textDocument/semanticTokens/full
  - textDocument/inlayHint
  - textDocument/codeAction
  - textDocument/publishDiagnostics

Protocolo: JSON-RPC 2.0 sobre stdio.

NOTA: usa I/O em modo binário (`sys.stdin.buffer`). O `Content-Length`
é sempre em BYTES (spec LSP), e o Python em modo texto lê CARACTERES,
o que quebra com UTF-8 multi-byte (acentos, emojis).

QUALIFICAÇÃO DE NOMES (Sprint 6a):
  Símbolos de topo (funções, structs, enums, traits) usam chave simples
  (`main`, `Pessoa`). Locais (variáveis dentro de funções/métodos) usam
  chave qualificada (`main::i`, `helper::i`), porque dois escopos podem
  ter o mesmo nome. `scope_map` permite descobrir o enclosing function
  de qualquer posição do cursor.

REFERÊNCIAS COM ESCOPO (Sprint 8a):
  Quando o cursor está sobre uma variável LOCAL do enclosing function,
  `references` e `rename` filtram para apenas as ocorrências dentro
  dessa função. Símbolos de topo continuam com varredura léxica global.

INLAY HINTS + CODE ACTIONS (Sprint 12):
  Inlay hints mostram o tipo inferido para variáveis declaradas sem 
  anotação de tipo (`let x = 10` exibe `: int`). 
  Code actions permitem transformar essa sugestão em código real.
"""
import bisect
import sys
import json
import re

from lumina.ast import (
    Function, VarDecl, StructDecl, EnumDecl, TraitDecl, ImplBlock,
    IfStmt, WhileStmt, ForStmt, MatchStmt, DeferStmt, BenchStmt,
)
from lumina.lexer import Lexer
from lumina.lexer.tokens import TokenType
from lumina.parser import Parser
from lumina.semantic import SemanticAnalyzer
from lumina.errors import LuminaError


# ============================================================
# LSP SymbolKind
# ============================================================
SK_FILE = 1
SK_NAMESPACE = 3
SK_CLASS = 5
SK_METHOD = 6
SK_FIELD = 8
SK_ENUM = 10
SK_INTERFACE = 11
SK_FUNCTION = 12
SK_VARIABLE = 13
SK_CONSTANT = 14


# ============================================================
# Semantic token types
# ============================================================
TT_NAMESPACE = 0
TT_TYPE = 1
TT_CLASS = 2
TT_ENUM = 3
TT_INTERFACE = 4
TT_STRUCT = 5
TT_TYPE_PARAMETER = 6
TT_PARAMETER = 7
TT_VARIABLE = 8
TT_PROPERTY = 9
TT_ENUM_MEMBER = 10
TT_EVENT = 11
TT_FUNCTION = 12
TT_METHOD = 13
TT_MACRO = 14
TT_KEYWORD = 15
TT_MODIFIER = 16
TT_COMMENT = 17
TT_STRING = 18
TT_NUMBER = 19
TT_REGEXP = 20
TT_OPERATOR = 21

SEMANTIC_TOKEN_TYPES = [
    "namespace", "type", "class", "enum", "interface",
    "struct", "typeParameter", "parameter", "variable", "property",
    "enumMember", "event", "function", "method", "macro",
    "keyword", "modifier", "comment", "string", "number",
    "regexp", "operator",
]

SEMANTIC_TOKEN_MODIFIERS = [
    "declaration", "definition", "readonly", "static",
    "deprecated", "abstract", "async", "modification",
    "documentation", "defaultLibrary",
]


# ============================================================
# Protocolo JSON-RPC (binário!)
# ============================================================
def read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        try:
            key, value = line.decode('ascii').split(': ', 1)
        except ValueError:
            continue
        headers[key] = value
    content_length = int(headers.get('Content-Length', 0))
    if content_length <= 0:
        return None
    body_bytes = sys.stdin.buffer.read(content_length)
    if not body_bytes:
        return None
    return json.loads(body_bytes.decode('utf-8'))


def write_message(msg):
    body_bytes = json.dumps(msg, ensure_ascii=False).encode('utf-8')
    header = f"Content-Length: {len(body_bytes)}\r\n\r\n".encode('ascii')
    sys.stdout.buffer.write(header)
    sys.stdout.buffer.write(body_bytes)
    sys.stdout.buffer.flush()


# ============================================================
# Helpers de posição
# ============================================================
def get_word_at_position(text, line, char):
    lines = text.split('\n')
    if line >= len(lines):
        return ""
    line_str = lines[line]
    if char > len(line_str):
        return ""
    start = char
    while start > 0 and (line_str[start - 1].isalnum() or line_str[start - 1] == '_'):
        start -= 1
    end = char
    while end < len(line_str) and (line_str[end].isalnum() or line_str[end] == '_'):
        end += 1
    return line_str[start:end]


def find_word_range(text, line, char):
    lines = text.split('\n')
    if line >= len(lines):
        return None
    line_str = lines[line]
    if char > len(line_str):
        return None
    if char == len(line_str) or not (line_str[char].isalnum() or line_str[char] == '_'):
        if char == 0:
            return None
        if not (line_str[char - 1].isalnum() or line_str[char - 1] == '_'):
            return None
        char = char - 1
    start = char
    while start > 0 and (line_str[start - 1].isalnum() or line_str[start - 1] == '_'):
        start -= 1
    end = char
    while end < len(line_str) and (line_str[end].isalnum() or line_str[end] == '_'):
        end += 1
    return (start, end)


def _build_line_starts(source):
    starts = [0]
    for i, c in enumerate(source):
        if c == '\n':
            starts.append(i + 1)
    return starts


def _offset_to_linecol(starts, offset):
    line = bisect.bisect_right(starts, offset) - 1
    col = offset - starts[line]
    return line, col


def _expand_range_to_word(text, rng):
    """Expande um Range LSP para cobrir a palavra inteira."""
    line = rng["start"]["line"]
    col = rng["start"]["character"]
    lines = text.split('\n')
    if line >= len(lines):
        return rng
    line_str = lines[line]
    end = col
    while end < len(line_str) and (line_str[end].isalnum() or line_str[end] == '_'):
        end += 1
    return {
        "start": {"line": line, "character": col},
        "end": {"line": line, "character": end},
    }


# ============================================================
# AST helpers
# ============================================================
def _fmt_params(params):
    out = []
    for p in params:
        if hasattr(p, 'name'):
            out.append(f"{p.name}: {p.type_ann}")
        elif isinstance(p, tuple) and len(p) >= 2:
            out.append(f"{p[0]}: {p[1]}")
    return ", ".join(out)


def _range_around(line, col, length):
    l0 = max(0, (line or 1) - 1)
    c0 = max(0, (col or 1) - 1)
    return {
        "start": {"line": l0, "character": c0},
        "end": {"line": l0, "character": c0 + max(1, length)},
    }


def _walk_stmts(stmts, callback):
    """Walk genérico (sem contexto)."""
    if not stmts:
        return
    for stmt in stmts:
        if stmt is None:
            continue
        callback(stmt)
        if isinstance(stmt, IfStmt):
            _walk_stmts(stmt.then_body, callback)
            if stmt.else_body:
                _walk_stmts(stmt.else_body, callback)
        elif isinstance(stmt, WhileStmt):
            _walk_stmts(stmt.body, callback)
        elif isinstance(stmt, ForStmt):
            _walk_stmts(stmt.body, callback)
        elif isinstance(stmt, MatchStmt):
            for case in stmt.cases:
                if len(case) >= 4:
                    _walk_stmts(case[3], callback)
            if stmt.default:
                _walk_stmts(stmt.default, callback)
        elif isinstance(stmt, DeferStmt):
            _walk_stmts(stmt.body, callback)
        elif isinstance(stmt, BenchStmt):
            _walk_stmts(stmt.body, callback)


def _walk_stmts_with_context(stmts, callback, ctx_name):
    """Walk que passa `ctx_name` (função/método) ao callback.

    Usado para registrar locais com chave qualificada (`main::i`).
    """
    _walk_stmts(stmts, lambda s: callback(s, ctx_name))


def _find_all_references(code, names):
    """Varredura léxica global.

    Retorna TODAS as ocorrências de cada nome. Não distingue escopos —
    o filtro por escopo é feito em `LuminaLSP._filter_refs_for_scope`.
    """
    result = {n: [] for n in names}
    lines = code.split('\n')
    for i, line_str in enumerate(lines):
        if line_str.strip().startswith('#'):
            continue
        for name in names:
            for match in re.finditer(r'\b' + re.escape(name) + r'\b', line_str):
                result[name].append({
                    "line": i,
                    "col": match.start(),
                    "end_col": match.end(),
                })
    return result


def _extract_suggestion(message):
    """Extrai 'X' de 'Você quis dizer X?' da mensagem."""
    m = re.search(r"Você quis dizer '([^']+)'\?", message)
    if m:
        return m.group(1)
    return None


def _qualify(func_name, var_name):
    """Chave qualificada para locais."""
    return f"{func_name}::{var_name}"


# ============================================================
# Análise do documento
# ============================================================
def validate_and_extract_symbols(code):
    """Parse + semantic + extração de símbolos.

    Retorna (9-tuple):
      diagnostics, symbols, definitions, symbol_details,
      document_symbols, references, scope_map, semantic_tokens, inlay_hints
    """
    diagnostics = []
    symbols = {"functions": [], "vars": []}
    definitions = {}
    symbol_details = {}
    document_symbols = []
    no_type_var_decls = []
    scope_map = []
    _stmt_refs = {}
    semantic_tokens = []
    inlay_hints = []

    try:
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, "lsp.lm", code)
        ast = parser.parse()

        # ----- Passada 0: captura VarDecls sem tipo + constrói scope_map -----
        def _capture(stmt, ctx):
            if isinstance(stmt, VarDecl) and stmt.var_type is None:
                no_type_var_decls.append(stmt)

        for decl in ast:
            if isinstance(decl, Function):
                start = getattr(decl, 'line', 0) or 0
                scope_map.append((start, decl.name))
                _walk_stmts_with_context(decl.body, _capture, decl.name)
            elif isinstance(decl, ImplBlock):
                for m in decl.methods:
                    start = getattr(m, 'line', 0) or 0
                    scope_map.append((start, m.name))
                    _walk_stmts_with_context(m.body, _capture, m.name)

        scope_map.sort()

        # ----- Passada 1: top-level -----
        for decl in ast:
            if isinstance(decl, Function):
                params_str = _fmt_params(decl.params)
                ret = f" -> {decl.return_type}" if decl.return_type != "void" else ""
                detail = f"fn {decl.name}({params_str}){ret}"
                symbols["functions"].append({"name": decl.name, "detail": detail, "line": decl.line})
                definitions[decl.name] = {"line": decl.line - 1, "col": decl.col - 1}
                symbol_details[decl.name] = {
                    "kind": SK_FUNCTION, "detail": detail,
                    "line": decl.line, "col": decl.col,
                }

                children = []
                def _collect_child(stmt, ctx):
                    if isinstance(stmt, VarDecl):
                        qkey = _qualify(ctx, stmt.name)
                        if qkey not in symbol_details:
                            vt = stmt.var_type or "inferred"
                            symbol_details[qkey] = {
                                "kind": SK_VARIABLE,
                                "detail": f"{stmt.name}: {vt}",
                                "line": getattr(stmt, 'line', 0) or 0,
                                "col": getattr(stmt, 'col', 0) or 0,
                            }
                            definitions[qkey] = {
                                "line": max(0, (getattr(stmt, 'line', 1) or 1) - 1),
                                "col": max(0, (getattr(stmt, 'col', 1) or 1) - 1),
                            }
                            _stmt_refs[qkey] = stmt
                        child_detail = f"{stmt.name}: {stmt.var_type or 'inferred'}"
                        children.append({
                            "name": stmt.name,
                            "detail": child_detail,
                            "kind": SK_VARIABLE,
                            "range": _range_around(
                                getattr(stmt, 'line', 1),
                                getattr(stmt, 'col', 1),
                                len(stmt.name),
                            ),
                            "selectionRange": _range_around(
                                getattr(stmt, 'line', 1),
                                getattr(stmt, 'col', 1),
                                len(stmt.name),
                            ),
                        })
                _walk_stmts_with_context(decl.body, _collect_child, decl.name)

                document_symbols.append({
                    "name": decl.name, "detail": detail, "kind": SK_FUNCTION,
                    "range": _range_around(decl.line, decl.col, len(decl.name)),
                    "selectionRange": _range_around(decl.line, decl.col, len(decl.name)),
                    "children": children,
                })

            elif isinstance(decl, StructDecl):
                fields_str = ", ".join(f"{k}: {v}" for k, v in decl.fields.items())
                detail = f"struct {decl.name} {{ {fields_str} }}"
                symbol_details[decl.name] = {
                    "kind": SK_CLASS, "detail": detail,
                    "line": getattr(decl, 'line', 0) or 0,
                    "col": getattr(decl, 'col', 0) or 0,
                }
                definitions[decl.name] = {
                    "line": getattr(decl, 'line', 1) - 1,
                    "col": getattr(decl, 'col', 1) - 1,
                }
                document_symbols.append({
                    "name": decl.name, "detail": detail, "kind": SK_CLASS,
                    "range": _range_around(getattr(decl, 'line', 1), getattr(decl, 'col', 1), len(decl.name)),
                    "selectionRange": _range_around(getattr(decl, 'line', 1), getattr(decl, 'col', 1), len(decl.name)),
                })

            elif isinstance(decl, EnumDecl):
                variants_str = ", ".join(v[0] for v in decl.variants)
                detail = f"enum {decl.name} {{ {variants_str} }}"
                symbol_details[decl.name] = {
                    "kind": SK_ENUM, "detail": detail,
                    "line": getattr(decl, 'line', 0) or 0,
                    "col": getattr(decl, 'col', 0) or 0,
                }
                document_symbols.append({
                    "name": decl.name, "detail": detail, "kind": SK_ENUM,
                    "range": _range_around(getattr(decl, 'line', 1), getattr(decl, 'col', 1), len(decl.name)),
                    "selectionRange": _range_around(getattr(decl, 'line', 1), getattr(decl, 'col', 1), len(decl.name)),
                })

            elif isinstance(decl, TraitDecl):
                methods_str = ", ".join(m.name for m in decl.methods)
                detail = f"trait {decl.name} {{ {methods_str} }}"
                symbol_details[decl.name] = {
                    "kind": SK_INTERFACE, "detail": detail,
                    "line": getattr(decl, 'line', 0) or 0,
                    "col": getattr(decl, 'col', 0) or 0,
                }
                document_symbols.append({
                    "name": decl.name, "detail": detail, "kind": SK_INTERFACE,
                    "range": _range_around(getattr(decl, 'line', 1), getattr(decl, 'col', 1), len(decl.name)),
                    "selectionRange": _range_around(getattr(decl, 'line', 1), getattr(decl, 'col', 1), len(decl.name)),
                })

            elif isinstance(decl, ImplBlock):
                methods = []
                for m in decl.methods:
                    params_str = _fmt_params(m.params)
                    ret = f" -> {m.return_type}" if m.return_type != "void" else ""
                    mdetail = f"fn {m.name}({params_str}){ret}"

                    mchildren = []
                    def _collect_method_local(stmt, ctx):
                        if isinstance(stmt, VarDecl):
                            qkey = _qualify(ctx, stmt.name)
                            if qkey not in symbol_details:
                                vt = stmt.var_type or "inferred"
                                symbol_details[qkey] = {
                                    "kind": SK_VARIABLE,
                                    "detail": f"{stmt.name}: {vt}",
                                    "line": getattr(stmt, 'line', 0) or 0,
                                    "col": getattr(stmt, 'col', 0) or 0,
                                }
                                definitions[qkey] = {
                                    "line": max(0, (getattr(stmt, 'line', 1) or 1) - 1),
                                    "col": max(0, (getattr(stmt, 'col', 1) or 1) - 1),
                                }
                                _stmt_refs[qkey] = stmt
                            mchildren.append({
                                "name": stmt.name,
                                "detail": f"{stmt.name}: {stmt.var_type or 'inferred'}",
                                "kind": SK_VARIABLE,
                                "range": _range_around(
                                    getattr(stmt, 'line', 1),
                                    getattr(stmt, 'col', 1),
                                    len(stmt.name),
                                ),
                                "selectionRange": _range_around(
                                    getattr(stmt, 'line', 1),
                                    getattr(stmt, 'col', 1),
                                    len(stmt.name),
                                ),
                            })
                    _walk_stmts_with_context(m.body, _collect_method_local, m.name)

                    methods.append({
                        "name": m.name, "detail": mdetail, "kind": SK_METHOD,
                        "range": _range_around(getattr(m, 'line', 1), getattr(m, 'col', 1), len(m.name)),
                        "selectionRange": _range_around(getattr(m, 'line', 1), getattr(m, 'col', 1), len(m.name)),
                        "children": mchildren,
                    })
                    symbol_details[m.name] = {
                        "kind": SK_METHOD, "detail": mdetail,
                        "line": getattr(m, 'line', 0) or 0,
                        "col": getattr(m, 'col', 0) or 0,
                    }
                    definitions[m.name] = {
                        "line": getattr(m, 'line', 1) - 1,
                        "col": getattr(m, 'col', 1) - 1,
                    }
                document_symbols.append({
                    "name": decl.struct_name,
                    "detail": f"impl {decl.struct_name}",
                    "kind": SK_NAMESPACE,
                    "range": _range_around(getattr(decl, 'line', 1), getattr(decl, 'col', 1), len(decl.struct_name)),
                    "selectionRange": _range_around(getattr(decl, 'line', 1), getattr(decl, 'col', 1), len(decl.struct_name)),
                    "children": methods,
                })

            elif isinstance(decl, VarDecl):
                var_type = decl.var_type or "inferred"
                symbols["vars"].append({
                    "name": decl.name, "detail": f"{decl.name}: {var_type}",
                    "line": getattr(decl, 'line', 0),
                })
                definitions[decl.name] = {
                    "line": getattr(decl, 'line', 1) - 1,
                    "col": getattr(decl, 'col', 1) - 1,
                }
                symbol_details[decl.name] = {
                    "kind": SK_VARIABLE, "detail": f"{decl.name}: {var_type}",
                    "line": getattr(decl, 'line', 0) or 0,
                    "col": getattr(decl, 'col', 0) or 0,
                }
                document_symbols.append({
                    "name": decl.name,
                    "detail": f"{decl.name}: {var_type}",
                    "kind": SK_VARIABLE,
                    "range": _range_around(getattr(decl, 'line', 1), getattr(decl, 'col', 1), len(decl.name)),
                    "selectionRange": _range_around(getattr(decl, 'line', 1), getattr(decl, 'col', 1), len(decl.name)),
                })

        # ----- Passada 2: semantic -----
        analyzer = SemanticAnalyzer("lsp.lm", code)
        analyzer.analyze(ast)

        # Passada 3: atualiza detail dos locais com tipo inferido.
        for qkey, stmt in _stmt_refs.items():
            info = symbol_details.get(qkey)
            if info is None:
                continue
            inferred = stmt.var_type or "inferred"
            base_name = qkey.split("::")[-1]
            info["detail"] = f"{base_name}: {inferred}"

        # ----- Passada 4: Semantic Tokens + Inlay Hints -----
        semantic_tokens = _collect_semantic_tokens(code, tokens, ast, symbol_details)
        inlay_hints = _collect_inlay_hints(no_type_var_decls)

    except LuminaError as e:
        diagnostics.append({
            "range": {
                "start": {"line": max(0, e.line - 1), "character": max(0, e.col - 1)},
                "end": {"line": max(0, e.line - 1), "character": max(1, e.col)},
            },
            "severity": 1,
            "source": "lumina",
            "message": e.message,
        })
    except Exception:
        pass

    # References: só para top-level. Locais são filtrados por escopo
    # em `LuminaLSP._filter_refs_for_scope` no momento da query.
    top_level_names = [k for k in symbol_details.keys() if "::" not in k]
    references = _find_all_references(code, top_level_names)

    return (diagnostics, symbols, definitions, symbol_details,
            document_symbols, references, scope_map, semantic_tokens, inlay_hints)


# ============================================================
# Semantic tokens
# ============================================================
def _build_name_to_type(symbol_details):
    """Mapeia nome simples → tokenType (sem distinguir escopo)."""
    mapping = {}
    for key, info in symbol_details.items():
        name = key.split("::")[-1]
        kind = info.get('kind')
        if kind == SK_FUNCTION:
            mapping[name] = TT_FUNCTION
        elif kind == SK_METHOD:
            mapping[name] = TT_METHOD
        elif kind == SK_CLASS:
            mapping[name] = TT_CLASS
        elif kind == SK_ENUM:
            mapping[name] = TT_ENUM
        elif kind == SK_INTERFACE:
            mapping[name] = TT_INTERFACE
        elif kind == SK_VARIABLE:
            mapping[name] = TT_VARIABLE
    return mapping


def _collect_semantic_tokens(code, tokens, ast, symbol_details):
    name_to_type = _build_name_to_type(symbol_details)

    for decl in ast:
        if isinstance(decl, EnumDecl):
            for vname, _payloads in decl.variants:
                name_to_type[vname] = TT_ENUM_MEMBER

    for decl in ast:
        if isinstance(decl, Function):
            for p in decl.params:
                pname = p.name if hasattr(p, 'name') else p[0]
                name_to_type[pname] = TT_PARAMETER
        elif isinstance(decl, ImplBlock):
            for m in decl.methods:
                for p in m.params:
                    pname = p.name if hasattr(p, 'name') else p[0]
                    name_to_type[pname] = TT_PARAMETER

    starts = _build_line_starts(code)
    result = []
    prev_line = 0
    prev_col = 0

    for tok in tokens:
        if tok.type != TokenType.IDENT:
            continue
        tt = name_to_type.get(tok.value)
        if tt is None:
            continue
        start_offset = tok.offset - len(tok.value)
        if start_offset < 0:
            continue
        try:
            line, col = _offset_to_linecol(starts, start_offset)
        except Exception:
            continue
        delta_line = line - prev_line
        delta_col = col - prev_col if delta_line == 0 else col
        result.extend([delta_line, delta_col, len(tok.value), tt, 0])
        prev_line = line
        prev_col = col

    return result


# ============================================================
# Inlay hints
# ============================================================
def _collect_inlay_hints(no_type_var_decls):
    hints = []
    for decl in no_type_var_decls:
        # O analyzer atualiza in-place o 'var_type' dos nós da AST.
        inferred = getattr(decl, 'var_type', None)
        if not inferred or inferred == "inferred":
            continue
        line = getattr(decl, 'line', 0) or 0
        col = getattr(decl, 'col', 0) or 0
        if line <= 0 or col <= 0:
            continue
        hints.append({
            "position": {
                "line": line - 1,
                "character": (col - 1) + len(decl.name),
            },
            "label": f": {inferred}",
            "kind": 1,
            "paddingLeft": False,
            "paddingRight": False,
        })
    return hints


# ============================================================
# Servidor LSP
# ============================================================
class LuminaLSP:
    def __init__(self):
        self.latest_text = ""
        self.latest_definitions = {}
        self.symbols = {"functions": [], "vars": []}
        self.symbol_details = {}
        self.document_symbols = []
        self.references = {}
        self.latest_uri = ""
        self.semantic_tokens_data = []
        self.inlay_hints_data = []
        self.last_diagnostics = []
        self.scope_map = []   # [(start_line, func_name), ...] ordenado

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    def _enclosing_func(self, line):
        """Encontra a função cujo `start_line` <= `line` está mais próxima.

        `line` é 0-based (formato LSP). `scope_map` está 1-based,
        então convertemos.
        """
        target = line + 1
        best = None
        for start, name in self.scope_map:
            if start <= target:
                best = name
            else:
                break
        return best

    def _lookup(self, table, name, line):
        """Tenta a chave qualificada primeiro; cai para simples."""
        func = self._enclosing_func(line)
        if func is not None:
            qualified = f"{func}::{name}"
            if qualified in table:
                return table[qualified]
        if name in table:
            return table[name]
        return None

    def _build_func_ranges(self):
        """Constrói `{func_name: (start_line, end_line)}` 1-based.

        End line da função N é `start_line` da função N+1 - 1.
        Para a última função, é o total de linhas do arquivo.
        """
        total_lines = self.latest_text.count('\n') + 1
        ranges = {}
        for i, (start, name) in enumerate(self.scope_map):
            if i + 1 < len(self.scope_map):
                end = self.scope_map[i + 1][0] - 1
            else:
                end = total_lines
            ranges[name] = (start, end)
        return ranges

    def _filter_refs_for_scope(self, word, refs, cursor_line):
        """Filtra refs para o escopo do cursor.

        Se `word` é uma variável LOCAL do enclosing function (chave
        qualificada `func::word` presente em `symbol_details`),
        mantém apenas as ocorrências dentro do range dessa função.
        Caso contrário, retorna todas (varredura léxica).

        `cursor_line` é 0-based (LSP); `refs` usam linhas 0-based.
        """
        enclosing = self._enclosing_func(cursor_line)
        if enclosing is None:
            return refs

        qkey = f"{enclosing}::{word}"
        if qkey not in self.symbol_details:
            return refs

        ranges = self._build_func_ranges()
        func_range = ranges.get(enclosing)
        if not func_range:
            return refs

        start_1b, end_1b = func_range
        return [
            r for r in refs
            if (start_1b - 1) <= r["line"] <= (end_1b - 1)
        ]

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------
    def run(self):
        while True:
            try:
                msg = read_message()
            except Exception as e:
                sys.stderr.write(f"[lumina-lsp] read_message error: {e}\n")
                continue

            if not msg:
                break

            method = msg.get("method")
            params = msg.get("params", {})
            msg_id = msg.get("id")

            try:
                if method == "initialize":
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": {
                            "capabilities": {
                                "textDocumentSync": 1,
                                "completionProvider": {
                                    "resolveProvider": False,
                                    "triggerCharacters": ["", "."],
                                },
                                "hoverProvider": True,
                                "definitionProvider": True,
                                "referencesProvider": True,
                                "renameProvider": {"prepareProvider": True},
                                "documentSymbolProvider": True,
                                "semanticTokensProvider": {
                                    "legend": {
                                        "tokenTypes": SEMANTIC_TOKEN_TYPES,
                                        "tokenModifiers": SEMANTIC_TOKEN_MODIFIERS,
                                    },
                                    "full": True,
                                },
                                "inlayHintProvider": True,
                                "codeActionProvider": {
                                    "codeActionKinds": ["quickfix", "refactor.rewrite"],
                                },
                            }
                        }
                    })

                elif method in ("textDocument/didOpen", "textDocument/didChange"):
                    text = params.get("textDocument", {}).get("text", "")
                    if not text:
                        changes = params.get("contentChanges", [])
                        if changes:
                            text = changes[0].get("text", "")

                    self.latest_text = text
                    self.latest_uri = params.get("textDocument", {}).get("uri", "")

                    (diagnostics, symbols, defs, details,
                     doc_syms, refs, scope_map, sem_tokens, inlay_hints) = \
                        validate_and_extract_symbols(text)

                    self.latest_definitions = defs
                    self.symbols = symbols
                    self.symbol_details = details
                    self.document_symbols = doc_syms
                    self.references = refs
                    self.last_diagnostics = diagnostics
                    self.scope_map = scope_map
                    self.semantic_tokens_data = sem_tokens
                    self.inlay_hints_data = inlay_hints

                    write_message({
                        "jsonrpc": "2.0",
                        "method": "textDocument/publishDiagnostics",
                        "params": {
                            "uri": self.latest_uri,
                            "diagnostics": diagnostics,
                        }
                    })

                elif method == "textDocument/completion":
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": {"isIncomplete": False, "items": self.get_completions()}
                    })

                elif method == "textDocument/hover":
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": self.get_hover(params),
                    })

                elif method == "textDocument/definition":
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": self.get_definition(params),
                    })

                elif method == "textDocument/references":
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": self.get_references(params),
                    })

                elif method == "textDocument/prepareRename":
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": self.prepare_rename(params),
                    })

                elif method == "textDocument/rename":
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": self.rename(params),
                    })

                elif method == "textDocument/documentSymbol":
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": self.document_symbols,
                    })

                elif method == "textDocument/semanticTokens/full":
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": {"data": self.semantic_tokens_data},
                    })

                elif method == "textDocument/inlayHint":
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": self.inlay_hints_data,
                    })

                elif method == "textDocument/codeAction":
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": self.get_code_actions(params),
                    })

                elif method == "shutdown":
                    write_message({"jsonrpc": "2.0", "id": msg_id, "result": None})

                elif method == "exit":
                    break

            except Exception as e:
                sys.stderr.write(f"[lumina-lsp] handler error ({method}): {e}\n")
                if msg_id is not None:
                    write_message({
                        "jsonrpc": "2.0", "id": msg_id,
                        "error": {"code": -32603, "message": str(e)},
                    })

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def get_completions(self):
        items = []
        keywords = [
            'fn', 'let', 'mut', 'if', 'elif', 'else', 'while', 'for', 'in',
            'return', 'print', 'true', 'false', 'match', 'case', 'default',
            'and', 'or', 'not', 'struct', 'enum', 'extern', 'import', 'defer',
            'break', 'continue', 'assert', 'bench', 'trait', 'comptime', 'as',
            'impl', 'switch', 'export', 'none', 'nil', 'quote',
        ]
        for kw in keywords:
            items.append({"label": kw, "kind": 14, "detail": "Lumina Keyword"})

        for func in self.symbols.get("functions", []):
            items.append({"label": func["name"], "kind": 3, "detail": func["detail"]})

        for var in self.symbols.get("vars", []):
            items.append({"label": var["name"], "kind": 6, "detail": var["detail"]})

        for key, info in self.symbol_details.items():
            if info["kind"] == SK_CLASS:
                name = key.split("::")[-1]
                items.append({"label": name, "kind": 7, "detail": info["detail"]})
            elif info["kind"] == SK_ENUM:
                name = key.split("::")[-1]
                items.append({"label": name, "kind": 13, "detail": info["detail"]})
            elif info["kind"] == SK_INTERFACE:
                name = key.split("::")[-1]
                items.append({"label": name, "kind": 8, "detail": info["detail"]})

        return items

    def get_hover(self, params):
        pos = params.get("position", {})
        line = pos.get("line", 0)
        word = get_word_at_position(
            self.latest_text, line, pos.get("character", 0)
        )
        if not word:
            return None

        info = self._lookup(self.symbol_details, word, line)
        if info:
            value = f"```lumina\n{info['detail']}\n```"
            return {"contents": {"kind": "markdown", "value": value}}
        return None

    def get_definition(self, params):
        pos = params.get("position", {})
        line = pos.get("line", 0)
        word = get_word_at_position(
            self.latest_text, line, pos.get("character", 0)
        )
        if not word:
            return None

        def_loc = self._lookup(self.latest_definitions, word, line)
        if not def_loc:
            return None
        return {
            "uri": self.latest_uri,
            "range": {
                "start": {"line": def_loc["line"], "character": def_loc["col"]},
                "end": {"line": def_loc["line"], "character": def_loc["col"] + len(word)},
            },
        }

    def get_references(self, params):
        pos = params.get("position", {})
        line = pos.get("line", 0)
        word = get_word_at_position(
            self.latest_text, line, pos.get("character", 0)
        )
        if not word:
            return []

        refs = self.references.get(word, [])
        # NOVO (Sprint 8a): filtra para o escopo do cursor se `word`
        # for uma variável local do enclosing function.
        refs = self._filter_refs_for_scope(word, refs, line)

        return [
            {
                "uri": self.latest_uri,
                "range": {
                    "start": {"line": r["line"], "character": r["col"]},
                    "end": {"line": r["line"], "character": r["end_col"]},
                },
            }
            for r in refs
        ]

    def prepare_rename(self, params):
        pos = params.get("position", {})
        line = pos.get("line", 0)
        char = pos.get("character", 0)
        word_range = find_word_range(self.latest_text, line, char)
        if not word_range:
            return None
        start, end = word_range
        return {
            "range": {
                "start": {"line": line, "character": start},
                "end": {"line": line, "character": end},
            },
            "placeholder": self.latest_text.split('\n')[line][start:end],
        }

    def rename(self, params):
        pos = params.get("position", {})
        line = pos.get("line", 0)
        new_name = params.get("newName", "")
        if not new_name:
            return None

        word = get_word_at_position(
            self.latest_text, line, pos.get("character", 0)
        )
        if not word:
            return None

        refs = self.references.get(word, [])
        # NOVO (Sprint 8a): mesma filtragem que `get_references`.
        refs = self._filter_refs_for_scope(word, refs, line)
        if not refs:
            return None

        edits = []
        for r in refs:
            edits.append({
                "range": {
                    "start": {"line": r["line"], "character": r["col"]},
                    "end": {"line": r["line"], "character": r["end_col"]},
                },
                "newText": new_name,
            })

        return {"changes": {self.latest_uri: edits}}

    def get_code_actions(self, params):
        context = params.get("context", {})
        diagnostics = context.get("diagnostics", [])
        actions = []

        # 1. Quickfix para sugestões de erros (ex: "Você quis dizer X?")
        for diag in diagnostics:
            msg = diag.get("message", "")
            suggestion = _extract_suggestion(msg)
            if not suggestion:
                continue
            original_range = diag.get("range", {})
            word_range = _expand_range_to_word(self.latest_text, original_range)
            start_line = word_range["start"]["line"]
            start_char = word_range["start"]["character"]
            end_char = word_range["end"]["character"]
            try:
                original_word = self.latest_text.split('\n')[start_line][start_char:end_char]
            except Exception:
                original_word = "?"
            if not original_word or original_word == suggestion:
                continue
            actions.append({
                "title": f"Renomear '{original_word}' para '{suggestion}'",
                "kind": "quickfix",
                "diagnostics": [diag],
                "isPreferred": True,
                "edit": {
                    "changes": {
                        self.latest_uri: [{
                            "range": word_range,
                            "newText": suggestion,
                        }],
                    },
                },
            })

        # 2. Code Action para aplicar Inlay Hint (Anotar tipo inferido)
        cursor_range = params.get("range", {})
        c_line = cursor_range.get("start", {}).get("line", 0)
        c_char = cursor_range.get("start", {}).get("character", 0)
        
        lines = self.latest_text.split('\n')
        if c_line < len(lines):
            line_str = lines[c_line]
            if c_char <= len(line_str):
                # Descobre a palavra sob o cursor
                word_start = c_char
                while word_start > 0 and (line_str[word_start-1].isalnum() or line_str[word_start-1] == '_'):
                    word_start -= 1
                word_end = c_char
                while word_end < len(line_str) and (line_str[word_end].isalnum() or line_str[word_end] == '_'):
                    word_end += 1
                word = line_str[word_start:word_end]
                
                if word:
                    # Verifica se existe um Inlay Hint para essa palavra
                    for hint in self.inlay_hints_data:
                        if hint["position"]["line"] == c_line:
                            hint_char = hint["position"]["character"]
                            # Se a palavra termina onde o hint começa
                            if word_end == hint_char or word_start <= hint_char <= word_end:
                                # Evita sugerir se já houver tipagem
                                rest_of_line = line_str[word_end:].strip()
                                if not rest_of_line.startswith(":"):
                                    inferred_type = hint["label"][2:] # remove ": "
                                    actions.append({
                                        "title": f"Anotar tipo inferido: {word}: {inferred_type}",
                                        "kind": "refactor.rewrite",
                                        "isPreferred": False,
                                        "edit": {
                                            "changes": {
                                                self.latest_uri: [{
                                                    "range": {
                                                        "start": {"line": c_line, "character": word_end},
                                                        "end": {"line": c_line, "character": word_end},
                                                    },
                                                    "newText": f": {inferred_type}"
                                                }]
                                            }
                                        }
                                    })
                                break

        return actions


if __name__ == "__main__":
    LuminaLSP().run()