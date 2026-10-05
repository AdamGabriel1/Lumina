"""`lumina bind` — gera bindings FFI a partir de um header C."""
import os
import re

from ..utils import Color, paint, success, warn
from .errors import report_error


def cmd_bind(header_file, output_name):
    if not os.path.exists(header_file):
        report_error(f"Arquivo '{header_file}' não encontrado.")
        return

    with open(header_file, "r") as f:
        content = f.read()

    pattern = r'(\w[\w\s\*]*?)\s+(\w+)\s*\(([^)]*)\)\s*;'
    matches = re.finditer(pattern, content)

    c_type_map = {
        "int": "int", "long": "int", "long long": "int",
        "short": "int", "size_t": "int",
        "float": "float", "double": "float",
        "char*": "str", "const char*": "str",
        "void*": "str", "const void*": "str",
        "char": "int", "unsigned char": "int",
        "unsigned int": "int", "unsigned long": "int",
    }

    lumina_decls = []
    for match in matches:
        c_ret = match.group(1).strip()
        name = match.group(2).strip()
        args_str = match.group(3).strip()

        if name in ("if", "while", "for", "return", "struct",
                    "typedef", "static", "extern", "void"):
            continue

        ret_type = c_type_map.get(c_ret, "str")

        lumina_args = []
        if args_str and args_str != "void":
            for arg in args_str.split(','):
                arg = arg.strip()
                parts = arg.rsplit(' ', 1)
                if len(parts) == 2:
                    arg_type, arg_name = parts[0].strip(), parts[1].strip()
                    lumina_type = c_type_map.get(arg_type, "str")
                    lumina_args.append(f"{arg_name}: {lumina_type}")
                else:
                    lumina_args.append("arg: str")

        lumina_decls.append(f"extern fn {name}({', '.join(lumina_args)}) -> {ret_type}")

    if not lumina_decls:
        warn("Nenhuma função válida encontrada no cabeçalho.")
        return

    out_file = f"std/{output_name}.lm"
    os.makedirs("std", exist_ok=True)
    with open(out_file, "w") as f:
        f.write(f"# Auto-gerado de {header_file} pelo Lumina Bind\n\n")
        f.write("\n".join(lumina_decls))

    success(f"✅ Bindings gerados em {paint(out_file, Color.BOLD + Color.BRIGHT_CYAN)} "
            f"({len(lumina_decls)} funções)")
