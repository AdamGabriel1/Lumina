import sys
import os

if __package__ in (None, ""):
    parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent not in sys.path:
        sys.path.insert(0, parent)
    __package__ = "lumina_cli"

from .utils import Color, paint, cprint, info, success, warn, error, step, header
from .commands import (
    cmd_new, cmd_build, cmd_clean, cmd_run, cmd_doc, cmd_install,
    cmd_bind, cmd_fmt, cmd_fmt_stdin, cmd_fmt_check_all, cmd_repl,
    cmd_test, cmd_check, set_error_format,
)
from .playground import run_server as run_playground
from .lint import lint_file

def usage():
    header("🌟 Lumina CLI")
    info("Uso: lumina <comando> [argumentos] [--error-format=text|json]")
    print()
    step("Comandos disponíveis:")
    commands = [
        ("new <nome>",                    "Cria um novo projeto Lumina"),
        ("build [arquivo] [flags]",       "Compila para binário nativo (-O2 padrão)"),
        ("run [arquivo]",                 "Compila e executa o binário nativo"),
        ("check [arquivo]",               "Só lexer+parser+semantic (rápido, sem codegen)"),
        ("test [arquivo]",                "Compila e executa a suíte de testes nativa"),
        ("jit [arquivo]",                 "Compila e executa via JIT (Just-In-Time)"),
        ("clean",                         "Limpa o cache e os binários gerados"),
        ("doc [flags]",                   "Gera documentação (--format=html|md|json)"),
        ("install",                       "Baixa/instala dependências do lumina.toml"),
        ("bind <header.h> <nome>",        "Gera bindings Lumina a partir de um header C"),
        ("fmt <arquivo.lm> [--check]",    "Formata (ou verifica) o código Lumina"),
        ("fmt --stdin",                   "Formata lido de stdin"),
        ("fmt --check-all <dir>",         "Verifica todos os .lm de um diretório"),
        ("repl",                          "Inicia o REPL interativo"),
        ("playground [porta]",            "Inicia o playground web (padrão: 8080)"),
        ("lint <arquivo> [flags]", "Análise estática (unused, shadow, unreachable)"),
    ]
    for cmd, desc in commands:
        print(f"  {paint(cmd, Color.BOLD + Color.BRIGHT_CYAN)}  {paint(desc, Color.MUTED)}")
    print()
    info(f"Flags de build: {paint('--release (-O3)', Color.MUTED)}, "
         f"{paint('--debug (-O0 + DWARF)', Color.MUTED)}, "
         f"{paint('--wasm', Color.MUTED)}, "
         f"{paint('--no-gc', Color.MUTED)}, "
         f"{paint('--linker=self|clang', Color.MUTED)}")
    info(f"Flags globais: {paint('--error-format=text|json', Color.MUTED)}, "
         f"{paint('--legacy-slice-copy', Color.MUTED)} (restaura cópia em v[a..b])")
    info(f"Exemplo: {paint('lumina new meu_projeto', Color.MUTED)}")


def main():
    """Entry point. Retorna exit code inteiro (0..255)."""
    args = sys.argv[1:]

    # --help / -h / help / sem args → usage + exit 0
    if not args or args[0] in ("-h", "--help", "help"):
        usage()
        return 0

    # ---- Extrai flags globais (--error-format, --legacy-slice-copy) ----
    error_format = "text"
    legacy_slice_copy = False
    filtered = []
    for arg in args:
        if arg.startswith("--error-format="):
            error_format = arg.split("=", 1)[1]
        elif arg == "--legacy-slice-copy":
            legacy_slice_copy = True
        else:
            filtered.append(arg)
    set_error_format(error_format)
    args = filtered

    # Propaga para o código (variável de ambiente simples).
    if legacy_slice_copy:
        os.environ["LUMINA_LEGACY_SLICE_COPY"] = "1"

    if not args:
        usage()
        return 0

    command = args[0]
    args = args[1:]

    if command == "new":
        if len(args) < 1:
            error("Uso: lumina new <nome_do_projeto>")
            return 1
        cmd_new(args[0])
        return 0

    elif command == "build":
        entry_file = None
        extra_flags = []
        for arg in args:
            if not arg.startswith('-') and not entry_file:
                entry_file = arg
            elif arg.startswith('-'):
                extra_flags.append(arg)
        result = cmd_build(entry_file, extra_flags)
        return 0 if result else 1

    elif command == "check":
        entry_file = args[0] if args and not args[0].startswith('-') else None
        return 0 if cmd_check(entry_file) else 1

    elif command == "test":
        entry_file = args[0] if args and not args[0].startswith('-') else None
        rc = cmd_test(entry_file)
        return rc if rc else 0

    elif command == "clean":
        cmd_clean()
        return 0

    elif command == "run":
        entry_file = args[0] if args and not args[0].startswith('-') else None
        extra_flags = [arg for arg in args if arg.startswith('-')]
        rc = cmd_run(entry_file, use_jit=False, extra_flags=extra_flags)
        return rc if rc else 0

    elif command == "jit":
        entry_file = args[0] if args and not args[0].startswith('-') else None
        cli_args = [a for a in args if not a.startswith('-')][1:]
        rc = cmd_run(entry_file, use_jit=True, cli_args=cli_args)
        return rc if rc else 0

    elif command == "doc":
        output_format = "html"
        output_path = None
        for arg in args:
            if arg.startswith("--format="):
                output_format = arg.split("=", 1)[1]
            elif arg.startswith("--output="):
                output_path = arg.split("=", 1)[1]
        cmd_doc(output_format=output_format, output_path=output_path)
        return 0

    elif command == "install":
        cmd_install()
        return 0

    elif command == "bind":
        if len(args) < 2:
            error("Uso: lumina bind <c_header.h> <nome_modulo>")
            return 1
        cmd_bind(args[0], args[1])
        return 0

    elif command == "fmt":
        check_only = "--check" in args
        from_stdin = "--stdin" in args
        check_all = "--check-all" in args
        files = [a for a in args if not a.startswith("--")]

        if from_stdin:
            ok = cmd_fmt_stdin(check_only=check_only)
            if check_only and not ok:
                return 1
            return 0 if ok else 1

        if check_all:
            directory = files[0] if files else "."
            ok = cmd_fmt_check_all(directory)
            return 0 if ok else 1

        if not files:
            error("Uso: lumina fmt <arquivo.lm> [--check | --stdin | --check-all <dir>]")
            return 1
        ok = cmd_fmt(files[0], check_only=check_only)
        if check_only and not ok:
            return 1
        return 0

    elif command == "repl":
        cmd_repl()
        return 0

    elif command == "playground":
        port = 8080
        if args and args[0].isdigit():
            port = int(args[0])
        run_playground(port=port)
        return 0

    elif command == "lint":
        fmt = "text"
        quiet = False
        files = []
        for arg in args:
            if arg.startswith("--format="):
                fmt = arg.split("=", 1)[1]
            elif arg == "--quiet":
                quiet = True
            else:
                files.append(arg)
        if not files:
            error("Uso: lumina lint <arquivo.lm> [--format=text|json] [--quiet]")
            return 1
        total = 0
        for f in files:
            total += len(lint_file(f, format=fmt, quiet=quiet))
        return min(total, 255)   # exit code satura em 255

    else:
        error(f"Comando desconhecido: {paint(command, Color.BOLD)}")
        print()
        usage()
        return 1


if __name__ == "__main__":
    sys.exit(main())