"""`lumina repl` — REPL persistente (estado sobrevive entre células)."""
import ctypes
import ctypes.util

from llvmlite import binding as llvm

from lumina.ast import (
    Function, StructDecl, EnumDecl, TraitDecl, ImplBlock,
    ImportStmt, ExternDecl, VarDecl,
)
from lumina.codegen import LLVMCodegen
from lumina.errors import LuminaError
from lumina.lexer import Lexer
from lumina.parser import Parser
from lumina.semantic import SemanticAnalyzer

from ..utils import Color, paint, cprint, info, success, warn, step
from .errors import report_error


def _repl_classify(cell_source: str) -> bool:
    """Retorna True se a célula é uma declaração top-level."""
    try:
        tokens = Lexer(cell_source).tokenize()
        parser = Parser(tokens, "<repl>", cell_source)
        ast = parser.parse()
    except Exception:
        return False

    if not ast:
        return False

    decl_types = (Function, StructDecl, EnumDecl, TraitDecl,
                  ImplBlock, ImportStmt, ExternDecl, VarDecl)
    return all(isinstance(n, decl_types) for n in ast)


def cmd_repl():
    step("Lumina REPL 2.0 — estado persistente")
    info("Digite seu código. Linha vazia executa.")
    info("Comandos:  :help   :history   :decls   :clear   exit")
    info(f"Dica: use {paint('mut x = 0', Color.BOLD)} no topo para "
         "estado que persiste. `let` é local à célula.")
    cprint("-" * 60, color=Color.MUTED)

    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    lib_c_path = ctypes.util.find_library('c')
    if lib_c_path:
        llvm.load_library_permanently(lib_c_path)

    gc_path = ctypes.util.find_library('gc')
    repl_use_gc = False
    if gc_path:
        try:
            llvm.load_library_permanently(gc_path)
            repl_use_gc = True
        except Exception:
            pass

    declarations = []
    cells = []
    buffer = []

    def _build_source():
        parts = list(declarations)
        for i, cell in enumerate(cells):
            indented = "\n".join("    " + ln for ln in cell.splitlines())
            parts.append(f"fn __cell_{i}() -> int:\n{indented}\n    return 0")
        parts.append("fn main() -> int:\n    return 0")
        return "\n".join(parts)

    def _eval(cell_source):
        is_decl = _repl_classify(cell_source)
        if is_decl:
            declarations.append(cell_source)
            exec_index = None
        else:
            exec_index = len(cells)
            cells.append(cell_source)

        full_source = _build_source()

        try:
            tokens = Lexer(full_source).tokenize()
            ast = Parser(tokens, "repl.lm", full_source).parse()
            SemanticAnalyzer("repl.lm", full_source).analyze(ast)
            codegen = LLVMCodegen(use_gc=repl_use_gc)
            llvm_ir = codegen.generate_module(ast)
            mod = llvm.parse_assembly(llvm_ir)
            mod.verify()
            target = llvm.Target.from_default_triple()
            tm = target.create_target_machine()
            engine = llvm.create_mcjit_compiler(mod, tm)
            engine.finalize_object()
            engine.run_static_constructors()

            if exec_index is not None:
                func_ptr = engine.get_function_address(f"__cell_{exec_index}")
                if func_ptr:
                    cfunc = ctypes.CFUNCTYPE(ctypes.c_int)(func_ptr)
                    ret = cfunc()
                    ctypes.CDLL(None).fflush(None)
                    if ret != 0:
                        print(f"=> {ret}")
        except LuminaError as e:
            if is_decl:
                declarations.pop()
            else:
                cells.pop()
            print(e)
        except Exception as e:
            if is_decl:
                declarations.pop()
            else:
                cells.pop()
            report_error(f"Erro interno: {e}")

    while True:
        try:
            prompt = "lumina> " if not buffer else "... "
            line = input(paint(prompt, Color.PROMPT))
            stripped = line.strip()

            if stripped in ("exit", "quit"):
                break

            if stripped == ":help":
                info("  :history  — tudo que foi digitado")
                info("  :decls    — só as declarações top-level")
                info("  :clear    — limpa o estado")
                info("  :help     — esta ajuda")
                info("  exit      — sair")
                continue

            if stripped == ":history":
                for i, d in enumerate(declarations):
                    cprint(f"[D{i}] {d}", color=Color.MUTED)
                for i, c in enumerate(cells):
                    cprint(f"[C{i}] {c}", color=Color.MUTED)
                if not declarations and not cells:
                    info("(vazio)")
                continue

            if stripped == ":decls":
                for i, d in enumerate(declarations):
                    cprint(f"[D{i}] {d}", color=Color.MUTED)
                if not declarations:
                    info("(nenhuma declaração)")
                continue

            if stripped == ":clear":
                declarations.clear()
                cells.clear()
                buffer.clear()
                success("Estado limpo.")
                continue

            if not stripped:
                if not buffer:
                    continue
                cell = "\n".join(buffer)
                buffer = []
                _eval(cell)
                continue

            buffer.append(line)

        except KeyboardInterrupt:
            warn("\n(Buffer limpo. Digite 'exit' para sair)")
            buffer = []
        except EOFError:
            break
