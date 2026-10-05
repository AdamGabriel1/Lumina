"""`lumina test` — compila e roda a suíte de testes nativa."""
import os
import subprocess

try:
    import tomllib
except ImportError:
    tomllib = None

from lumina.ast import (
    Function, CallExpr, NumberExpr, ReturnStmt, VariableExpr,
    VarDecl, AssignStmt, BinaryExpr,
)
from lumina.codegen import LLVMCodegen
from lumina.errors import LuminaError
from lumina.semantic import SemanticAnalyzer

from ..compiler import parse_module
from ..utils import Color, paint, warn, success, step, header
from .errors import report_error
from .linking import load_link_config, compile_extra_objects


def cmd_test(entry_file=None):
    """Executa a suíte de testes. Retorna o número de falhas (exit code)."""
    if not entry_file:
        if os.path.exists("lumina.toml") and tomllib:
            with open("lumina.toml", "rb") as f:
                config = tomllib.load(f)
                entry_file = config.get("package", {}).get("entry", "main.lm")
        elif os.path.exists("main.lm"):
            entry_file = "main.lm"
        else:
            report_error("Nenhum arquivo de entrada especificado.")
            return 1

    if not os.path.exists(entry_file):
        report_error(f"Arquivo '{entry_file}' não encontrado.")
        return 1

    step(f"🧪 Iniciando suíte de testes para: "
         f"{paint(entry_file, Color.BOLD + Color.BRIGHT_CYAN)}")

    try:
        ast = parse_module(entry_file)
    except LuminaError as e:
        report_error(e)
        return 1

    test_funcs = [d for d in ast if isinstance(d, Function) and d.name.startswith("test_")]
    if not test_funcs:
        warn("⚠️ Nenhuma função de teste (ex: `test \"nome\":`) encontrada no código.")
        return 0

    new_ast = [d for d in ast
               if not (isinstance(d, Function) and d.name == "main")]

    total_var = "_total_failures"
    body = [VarDecl(total_var, "int", NumberExpr("0"), True)]
    for func in test_funcs:
        call = CallExpr(VariableExpr(func.name, 0, 0), [])
        add = BinaryExpr("+", VariableExpr(total_var, 0, 0), call)
        body.append(AssignStmt(VariableExpr(total_var, 0, 0), add))
    body.append(ReturnStmt([VariableExpr(total_var, 0, 0)]))
    new_ast.append(Function("main", [], "int", body))

    try:
        with open(entry_file, "r") as f:
            source_code = f.read()
        analyzer = SemanticAnalyzer(entry_file, source_code)
        analyzer.analyze(new_ast)
    except LuminaError as e:
        report_error(e)
        return 1

    codegen = LLVMCodegen()
    codegen.escapes = analyzer.escapes
    codegen.freed_vars = getattr(analyzer, 'freed_vars', set())
    llvm_ir = codegen.generate_module(new_ast)

    ir_file = "lumina_test_runner.ll"
    binary_name = "lumina_test_bin"

    with open(ir_file, "w") as f:
        f.write(llvm_ir)

    link_cfg = load_link_config(entry_file)
    libs = link_cfg.get("libs", [])
    extra_objs_src = link_cfg.get("extra_objects", [])
    link_extra_flags = link_cfg.get("extra_flags", [])
    extra_obj_paths, has_cpp = compile_extra_objects(extra_objs_src, link_extra_flags)

    cmd_args = ["clang", "-O0", "-fprofile-instr-generate", "-fcoverage-mapping",
                ir_file, "-o", binary_name, "-lc", "-lm", "-lpthread", "-lgc"]
    cmd_args.extend(extra_obj_paths)
    if has_cpp:
        cmd_args.append("-lstdc++")
    for lib in libs:
        cmd_args.append(f"-l{lib}")
    cmd_args.extend(link_extra_flags)

    try:
        subprocess.run(cmd_args, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        header("Executando Testes")
        result = subprocess.run(
            [f"./{binary_name}"],
            capture_output=True, text=True,
            env={**os.environ, "LLVM_PROFILE_FILE": "lumina_test.profraw"},
        )
        print(result.stdout)

        if result.returncode == 0:
            success(f"✅ Todos os {len(test_funcs)} testes passaram!")
            if os.environ.get("LUMINA_NO_COVERAGE") == "1":
                return 0
            try:
                subprocess.run(
                    ["llvm-profdata", "merge", "-sparse",
                     "lumina_test.profraw", "-o", "lumina_test.profdata"],
                    check=True, capture_output=True, timeout=10,
                )
                header("📊 Relatório de Cobertura de Código")
                subprocess.run(
                    ["llvm-cov", "report", binary_name,
                     "-instr-profile=lumina_test.profdata"],
                    check=True, timeout=10,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                warn("⚠️ Relatório de cobertura ignorado (ferramenta ausente ou timeout).")
            except subprocess.CalledProcessError:
                warn("⚠️ llvm-cov report falhou; cobertura ignorada.")
            return 0
        else:
            report_error(f"{result.returncode} teste(s) falharam.")
            return result.returncode if result.returncode > 0 else 1

    except subprocess.CalledProcessError:
        report_error("Erro durante a compilação da suíte de testes.")
        return 1
    finally:
        for f in (ir_file, binary_name, "lumina_test.profraw", "lumina_test.profdata"):
            if os.path.exists(f):
                os.remove(f)
