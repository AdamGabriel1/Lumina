"""Auto-formatter: imprime a AST de volta como código Lumina."""
from lumina.ast import (
    Function, VarDecl, AssignStmt, ReturnStmt, IfStmt, WhileStmt, ForStmt,
    NumberExpr, StringExpr, VariableExpr, BinaryExpr, CallExpr,
    MemberExpr, SliceExpr, IndexExpr, ImportStmt, StructDecl, EnumDecl,
    TraitDecl, ImplBlock, ExternDecl, DestructureStmt, AddressOfExpr, DerefExpr,
    UnaryExpr, CastExpr, StructLiteralExpr, MatchExpr, LambdaExpr,
    DeferStmt, AssertStmt, BenchStmt, BreakStmt, ContinueStmt, NoneExpr,
    NilExpr, TypeAlias, ChainedComparisonExpr,
    QuoteExpr, UnquoteExpr, UnquoteSpliceExpr,
)
from lumina.ast.expressions import ArrayExpr, BoolExpr, PropagateExpr
from lumina.ast.statements import MatchStmt



def _fmt_params(params):
    """Formata parâmetros. Suporta `default` (Param.default)."""
    out = []
    for p in params:
        if hasattr(p, 'name'):
            name = p.name
            type_ann = p.type_ann
            default = getattr(p, 'default', None)
        else:
            name = p[0]
            type_ann = p[1]
            default = None

        s = f"{name}: {type_ann}"
        if default is not None:
            s += f" = {format_node(default, 0)}"
        out.append(s)
    return ", ".join(out)


def _format_attrs(node, indent):
    """Emite os `@nome`/`@nome(args)` anexados ao nó pelo parser."""
    attrs = getattr(node, 'attrs', None)
    if not attrs:
        return ""
    out = ""
    for item in attrs:
        if isinstance(item, tuple):
            name = item[0]
            args = item[1] if len(item) > 1 else []
        else:
            name, args = item, []
        if args:
            out += f"{indent}@{name}({', '.join(args)})\n"
        else:
            out += f"{indent}@{name}\n"
    return out


def format_node(node, indent_level=0):
    """Formata um nó, emitindo comentários leading e @attrs se houver."""
    indent = "    " * indent_level

    prefix = ""

    leading = getattr(node, 'leading_comments', None) or []
    for c in leading:
        prefix += _format_comment(c, indent)

    prefix += _format_attrs(node, indent)

    return prefix + _format_node_impl(node, indent_level)


def _format_comment(text, indent):
    """Reindenta um comentário (possivelmente multi-linha)."""
    lines = text.split('\n')
    return ''.join(f"{indent}{line.strip()}\n" for line in lines)


def _format_node_impl(node, indent_level=0):
    indent = "    " * indent_level

    if isinstance(node, Function):
        params = _fmt_params(node.params)
        ret = f" -> {node.return_type}" if node.return_type != "void" else ""
        prefix = "export " if getattr(node, 'is_exported', False) else ""
        prefix_newline = "\n" if indent_level == 0 else ""
        s = f"{prefix_newline}{indent}{prefix}fn {node.name}({params}){ret}:\n"
        for stmt in node.body:
            s += format_node(stmt, indent_level + 1)
        return s

    elif isinstance(node, StructDecl):
        prefix_newline = "\n" if indent_level == 0 else ""
        s = f"{prefix_newline}{indent}struct {node.name}"
        if node.type_params:
            s += f"<{', '.join(node.type_params)}>"
        s += ":\n"
        for fname, ftype in node.fields.items():
            s += f"{indent}    {fname}: {ftype}\n"
        return s

    elif isinstance(node, EnumDecl):
        prefix_newline = "\n" if indent_level == 0 else ""
        s = f"{prefix_newline}{indent}enum {node.name}:\n"
        for vname, payloads in node.variants:
            if isinstance(payloads, list):
                if payloads:
                    s += f"{indent}    {vname}({', '.join(payloads)})\n"
                else:
                    s += f"{indent}    {vname}\n"
            elif payloads:
                # legado: string única
                s += f"{indent}    {vname}({payloads})\n"
            else:
                s += f"{indent}    {vname}\n"
        return s
        
    elif isinstance(node, TraitDecl):
        prefix_newline = "\n" if indent_level == 0 else ""
        s = f"{prefix_newline}{indent}trait {node.name}:\n"
        for method in node.methods:
            # Emite comentários leading (o parser anexa em `leading_comments`)
            for c in (getattr(method, 'leading_comments', None) or []):
                for line in c.split('\n'):
                    s += f"{indent}    {line.strip()}\n"
            params = _fmt_params(method.params)
            ret = f" -> {method.return_type}" if method.return_type != "void" else ""
            s += f"{indent}    fn {method.name}({params}){ret}\n"
            # Corpo do método (se houver)
            for stmt in (method.body or []):
                s += format_node(stmt, indent_level + 2)
        return s

    elif isinstance(node, ImplBlock):
        prefix_newline = "\n" if indent_level == 0 else ""
        s = f"{prefix_newline}{indent}impl "
        if node.trait_name:
            s += f"{node.trait_name} for {node.struct_name}:\n"
        else:
            s += f"{node.struct_name}:\n"
        for method in node.methods:
            s += format_node(method, indent_level + 1)
        return s

    elif isinstance(node, ImportStmt):
        prefix_newline = "\n" if indent_level == 0 else ""
        return f'{prefix_newline}{indent}import "{node.filename}"\n'

    elif isinstance(node, TypeAlias):
        prefix_newline = "\n" if indent_level == 0 else ""
        params = getattr(node, 'type_params', None) or []
        params_str = f"<{', '.join(params)}>" if params else ""
        return f"{prefix_newline}{indent}type {node.name}{params_str} = {node.target_type}\n"

    elif isinstance(node, ExternDecl):
        prefix_newline = "\n" if indent_level == 0 else ""
        prefix = '"wasm" ' if getattr(node, 'is_wasm', False) else ''
        params = _fmt_params(node.params)
        ret = f" -> {node.return_type}" if node.return_type != "void" else ""
        return f"{prefix_newline}{indent}extern {prefix}fn {node.name}({params}){ret}\n"

    elif isinstance(node, VarDecl):
        mut = "mut " if node.is_mutable else "let "
        typ = f": {node.var_type}" if node.var_type else ""
        val = f" = {format_node(node.value, 0)}" if node.value else ""
        return f"{indent}{mut}{node.name}{typ}{val}\n"

    elif isinstance(node, DestructureStmt):
        mut = "mut " if node.is_mutable else "let "
        names = ", ".join(node.names)
        val = format_node(node.value, 0)
        return f"{indent}{mut}({names}) = {val}\n"

    elif isinstance(node, AssignStmt):
        target = format_node(node.target, 0)
        val = format_node(node.value, 0)
        return f"{indent}{target} = {val}\n"

    elif isinstance(node, ReturnStmt):
        vals = ", ".join([format_node(v, 0) for v in node.values])
        return f"{indent}return {vals}\n"

    elif isinstance(node, IfStmt):
        cond = format_node(node.condition, 0)
        prefix_newline = "\n" if indent_level > 0 else ""
        s = f"{prefix_newline}{indent}if {cond}:\n"
        for stmt in node.then_body:
            s += format_node(stmt, indent_level + 1)
        if node.else_body:
            s += f"{indent}else:\n"
            for stmt in node.else_body:
                s += format_node(stmt, indent_level + 1)
        return s

    elif isinstance(node, WhileStmt):
        cond = format_node(node.condition, 0)
        prefix_newline = "\n" if indent_level > 0 else ""
        s = f"{prefix_newline}{indent}while {cond}:\n"
        for stmt in node.body:
            s += format_node(stmt, indent_level + 1)
        return s

    elif isinstance(node, ForStmt):
        # Reconstrói o cabeçalho: `for i, x in ...` ou `for x in ...`
        var_repr = node.var_name
        if node.index_var is not None:
            var_repr = f"{node.index_var}, {node.var_name}"

        # v0.7.0: preserva a anotação `: T`.
        elem_annot = ""
        if getattr(node, 'elem_type', None):
            elem_annot = f": {node.elem_type}"

        if node.iterable:
            iter_val = format_node(node.iterable, 0)
            s = f"{indent}for {var_repr}{elem_annot} in {iter_val}:\n"
        else:
            start = format_node(node.start, 0)
            end = format_node(node.end, 0)
            s = f"{indent}for {var_repr}{elem_annot} in {start}..{end}:\n"
        for stmt in node.body:
            s += format_node(stmt, indent_level + 1)
        return s

    elif isinstance(node, MatchStmt):
        cond = format_node(node.condition, 0)
        s = f"{indent}match {cond}:\n"

        def _fmt_variant(v):
            if v is None:
                return "_"
            if isinstance(v, str):
                return v
            return format_node(v, 0)

        for case in node.cases:
            if len(case) == 4:
                variant_name, var_name, guard, body = case
            else:
                variant_name, var_name, body = case
                guard = None

            if isinstance(variant_name, list):
                variant_str = " | ".join(_fmt_variant(v) for v in variant_name)
            else:
                variant_str = _fmt_variant(variant_name)

            bind = f"({var_name})" if var_name else ""
            guard_str = f" if {format_node(guard, 0)}" if guard else ""
            s += f"{indent}    case {variant_str}{bind}{guard_str}:\n"
            for stmt in body:
                s += format_node(stmt, indent_level + 2)
        if node.default:
            s += f"{indent}    default:\n"
            for stmt in node.default:
                s += format_node(stmt, indent_level + 2)
        return s

    elif isinstance(node, DeferStmt):
        if len(node.body) == 1 and not isinstance(node.body[0], (IfStmt, WhileStmt, ForStmt, MatchStmt)):
            return f"{indent}defer {format_node(node.body[0], 0)}\n"
        s = f"{indent}defer:\n"
        for stmt in node.body:
            s += format_node(stmt, indent_level + 1)
        return s

    elif isinstance(node, AssertStmt):
        cond = format_node(node.condition, 0)
        return f"{indent}assert({cond})\n"

    elif isinstance(node, BenchStmt):
        s = f'{indent}bench "{node.name}":\n'
        for stmt in node.body:
            s += format_node(stmt, indent_level + 1)
        return s

    elif isinstance(node, (BreakStmt, ContinueStmt)):
        return f"{indent}{node.__class__.__name__.lower().replace('stmt', '')}\n"

    elif isinstance(node, NoneExpr):
        if indent_level > 0:
            return f"{indent}none\n"
        return "none"

    elif isinstance(node, NilExpr):
        if indent_level > 0:
            return f"{indent}nil\n"
        return "nil"

    elif isinstance(node, QuoteExpr):
        s = f"{indent}quote:\n"
        for stmt in node.statements:
            s += format_node(stmt, indent_level + 1)
        return s

    elif isinstance(node, UnquoteExpr):
        inner = format_node(node.expr, 0)
        if indent_level > 0:
            return f"{indent}~{inner}\n"
        return f"~{inner}"

    elif isinstance(node, UnquoteSpliceExpr):
        inner = format_node(node.expr, 0)
        if indent_level > 0:
            return f"{indent}~@{inner}\n"
        return f"~@{inner}"

    elif isinstance(node, NumberExpr):
        if indent_level > 0:
            return f"{indent}{node.value}\n"
        return node.value

    elif isinstance(node, BoolExpr):
        if indent_level > 0:
            return f"{indent}{'true' if node.value else 'false'}\n"
        return 'true' if node.value else 'false'

    elif isinstance(node, StringExpr):
        if indent_level > 0:
            return f'{indent}"{node.value}"\n'
        return f'"{node.value}"'

    elif isinstance(node, VariableExpr):
        if indent_level > 0:
            return f"{indent}{node.name}\n"
        return node.name

    elif isinstance(node, BinaryExpr):
        left = format_node(node.left, 0)
        right = format_node(node.right, 0)
        if indent_level > 0:
            return f"{indent}{left} {node.op} {right}\n"
        return f"{left} {node.op} {right}"

    elif isinstance(node, UnaryExpr):
        val = format_node(node.val, 0)
        if node.op == 'not':
            return f"not {val}"
        return f"{node.op}{val}"

    elif isinstance(node, CallExpr):
        callee_str = format_node(node.callee, 0)
        all_args = [format_node(a, 0) for a in node.args]
        for name, val in (getattr(node, 'kwargs', None) or []):
            all_args.append(f"{name}: {format_node(val, 0)}")
        args = ", ".join(all_args)
        if indent_level > 0:
            return f"{indent}{callee_str}({args})\n"
        return f"{callee_str}({args})"

    elif isinstance(node, MemberExpr):
        obj = format_node(node.obj, 0)
        op = "?." if node.is_safe else "."
        if indent_level > 0:
            return f"{indent}{obj}{op}{node.member}\n"
        return f"{obj}{op}{node.member}"

    elif isinstance(node, SliceExpr):
        arr = format_node(node.array, 0)
        start = format_node(node.start, 0) if node.start else ""
        end = format_node(node.end, 0) if node.end else ""
        if indent_level > 0:
            return f"{indent}{arr}[{start}..{end}]\n"
        return f"{arr}[{start}..{end}]"

    elif isinstance(node, IndexExpr):
        arr = format_node(node.array, 0)
        idx = format_node(node.index, 0)
        if indent_level > 0:
            return f"{indent}{arr}[{idx}]\n"
        return f"{arr}[{idx}]"

    elif isinstance(node, AddressOfExpr):
        return f"&{format_node(node.val, 0)}"

    elif isinstance(node, DerefExpr):
        return f"*{format_node(node.val, 0)}"

    elif isinstance(node, PropagateExpr):
        return f"{format_node(node.val, 0)}?"

    elif isinstance(node, CastExpr):
        return f"{format_node(node.expr, 0)} as {node.target_type}"

    elif isinstance(node, StructLiteralExpr):
        fields = ", ".join([f"{f.name}: {format_node(f.value, 0)}" for f in node.fields])
        return f"{node.struct_name} {{ {fields} }}"

    elif isinstance(node, MatchExpr):
        cond = format_node(node.condition, 0)
        s = f"match {cond} {{\n"
        for val, res in node.cases:
            s += f"{indent}    {format_node(val, 0)} => {format_node(res, 0)},\n"
        if node.default:
            s += f"{indent}    else => {format_node(node.default, 0)},\n"
        s += f"{indent}}}"
        return s

    elif isinstance(node, LambdaExpr):
        params = _fmt_params(node.params)
        ret = f" -> {node.return_type}" if node.return_type != "void" else ""
        if len(node.body) == 1:
            return f"fn({params}){ret}: {format_node(node.body[0], 0)}"
        s = f"fn({params}){ret}:\n"
        for stmt in node.body:
            s += format_node(stmt, indent_level + 1)
        return s

    elif isinstance(node, ArrayExpr):
        elements = ", ".join([format_node(el, 0) for el in node.elements])
        return f"[{elements}]"

    if isinstance(node, ChainedComparisonExpr):
        parts = [format_node(node.operands[0], 0)]
        for op, operand in zip(node.ops, node.operands[1:]):
            parts.append(op)
            parts.append(format_node(operand, 0))
        return " ".join(parts)

    return f"{indent}{str(node)}\n"