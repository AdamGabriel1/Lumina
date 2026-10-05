"""`lumina fmt` — formatação e verificação."""
import os
import sys

from lumina.errors import LuminaError
from lumina.lexer import Lexer
from lumina.parser import Parser

from ..compiler import format_node
from ..utils import Color, paint, info, success, warn
from .errors import report_error


def _format_source(source, filename):
    """Roda lexer + parser + format_node. Retorna a string formatada.

    Levanta LuminaError se o parsing falhar.
    """
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens, filename, source).parse()
    formatted = "".join(format_node(n) for n in ast)
    return formatted.lstrip("\n")


def cmd_fmt(filename, check_only=False):
    """Formata um arquivo Lumina."""
    if not os.path.exists(filename):
        report_error(f"Arquivo '{filename}' não encontrado.")
        return False

    with open(filename, "r") as f:
        original_code = f.read()

    try:
        formatted_code = _format_source(original_code, filename)
    except LuminaError as e:
        report_error(e)
        return False

    if check_only:
        if formatted_code == original_code:
            success(f"✅ {paint(filename, Color.BOLD)} — já formatado")
            return True
        info(f"⚠️  {paint(filename, Color.BOLD)} precisa ser formatado")
        return False

    with open(filename, "w") as f:
        f.write(formatted_code)

    success(f"✅ Arquivo '{paint(filename, Color.BOLD + Color.BRIGHT_CYAN)}' "
            f"formatado com sucesso!")
    return True


def cmd_fmt_stdin(check_only=False):
    """Lê código Lumina de stdin, formata, escreve em stdout."""
    source = sys.stdin.read()
    if not source.strip():
        return True

    try:
        formatted = _format_source(source, "<stdin>")
    except LuminaError as e:
        report_error(e)
        return False

    if check_only:
        return formatted == source

    sys.stdout.write(formatted)
    return True


def cmd_fmt_check_all(directory):
    """Verifica todos os .lm de um diretório."""
    import glob as _glob
    pattern = os.path.join(directory, "**", "*.lm")
    files = sorted(_glob.glob(pattern, recursive=True))
    if not files:
        warn(f"⚠️  Nenhum arquivo .lm encontrado em '{directory}'")
        return True

    bad = []
    for f in files:
        with open(f, "r") as fh:
            original = fh.read()
        try:
            formatted = _format_source(original, f)
        except LuminaError:
            bad.append(f)
            continue
        if formatted != original:
            bad.append(f)

    if bad:
        for f in bad:
            print(f"{f}: precisa ser formatado")
        info(f"📊 {len(bad)} de {len(files)} arquivos precisam ser formatados")
        return False

    success(f"✅ Todos os {len(files)} arquivos estão formatados")
    return True
