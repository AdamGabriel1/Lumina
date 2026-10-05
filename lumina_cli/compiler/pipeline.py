"""Pipeline principal: lexer → parser → semantic → codegen → IR → Otimização (O1)."""
import ctypes
import ctypes.util
import os

from llvmlite import binding as llvm

from lumina.codegen import LLVMCodegen
from lumina.errors import LuminaError
from lumina.semantic import SemanticAnalyzer

from ..utils import (
    Color, paint, info, success, warn, error, step, header,
    get_cache_hash,
)
from .parse import parse_module

# Inicializa o LLVM uma vez para habilitar os passes de otimização nativos
try:
    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
except Exception:
    pass


def _optimize_ir(llvm_ir, opt_level=1):
    """Roda passes de otimização no IR.

    A API do llvmlite mudou 3 vezes nos últimos anos:

      A) ~0.30–0.41: `llvm.create_pass_manager_builder()` + `pmb.populate(pm)`
      B) ~0.35–0.41: `llvm.PassManagerBuilder()` (classe alternativa)
      C) 0.42+:      API nova — `create_new_module_pass_manager()` +
                     passes individuais, ou `PassBuilder` + `runPasses`.

    Esta função detecta em runtime qual está disponível e tenta na
    ordem C → A → B. Se nada funcionar, retorna o IR intacto (sem
    warning ruidoso — a ausência de O1 interno não é fatal porque
    `--release` já roda `opt -O2` externamente em build.py).
    """
    try:
        mod = llvm.parse_assembly(llvm_ir)
        mod.verify()
    except Exception as e:
        warn(f"⚠️  Falha ao parsear IR para otimização: {e}. "
             f"Usando IR não-otimizado.")
        return llvm_ir

    # ------------------------------------------------------------------
    # API C (0.42+): New Pass Manager com passes individuais.
    # É o caminho que sua versão do llvmlite expõe.
    # ------------------------------------------------------------------
    if hasattr(llvm, 'create_new_module_pass_manager'):
        try:
            pm = llvm.create_new_module_pass_manager()

            # Sequência aproximando O1. Cada `add_*` é um passe do
            # New Pass Manager; a ordem importa (analyses antes de
            # transforms, cleanup no fim).
            _PASSES = (
                # Canonicalização e simplificação inicial
                "add_cfg_simplification_pass",
                "add_dead_code_elimination_pass",
                "add_instruction_combining_pass",
                "add_reassociate_expressions_pass",
                # Propagação interprocedural
                "add_ipsccp_pass",
                "add_global_optimizer_pass",
                "add_global_dce_pass",
                "add_dead_arg_elimination_pass",
                # Otimizações de função
                "add_function_attrs_pass",
                "add_gvn_pass",
                "add_promote_memory_to_register_pass",
                "add_tail_call_elimination_pass",
                "add_constant_merge_pass",
                # Cleanup final
                "add_cfg_simplification_pass",
                "add_dead_code_elimination_pass",
            )

            applied = 0
            for name in _PASSES:
                fn = getattr(pm, name, None)
                if fn is not None:
                    fn()
                    applied += 1

            if applied == 0:
                # API existe mas não expõe os passes que queremos.
                # Sem O1, mas sem warning — o `opt -O2` externo cobre.
                return llvm_ir

            pm.run(mod)
            return str(mod)
        except Exception:
            # Cai para as próximas tentativas silenciosamente.
            pass

    # ------------------------------------------------------------------
    # API A (0.30–0.41): builder + populate (legado).
    # ------------------------------------------------------------------
    if hasattr(llvm, 'create_pass_manager_builder'):
        try:
            pmb = llvm.create_pass_manager_builder()
            pmb.opt_level = opt_level
            pm = llvm.create_module_pass_manager()
            pmb.populate(pm)
            pm.run(mod)
            return str(mod)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # API B (0.35–0.41): classe PassManagerBuilder (legado alternativo).
    # ------------------------------------------------------------------
    if hasattr(llvm, 'PassManagerBuilder'):
        try:
            pmb = llvm.PassManagerBuilder()
            pmb.opt_level = opt_level
            pm = llvm.create_module_pass_manager()
            pmb.populate(pm)
            pm.run(mod)
            return str(mod)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Nenhuma API compatível. IR volta intacto. Sem warning — a
    # compilação com `--release` roda `opt -O2` externamente e a
    # ausência de O1 interno não degrada o resultado final.
    # ------------------------------------------------------------------
    return llvm_ir


def compile_lumina(filename, output_file="output.ll", use_cache=True,
                   is_wasm=False, is_debug=False, is_no_gc=False,
                   on_error=None, target_triple=None):
    cache_dir = ".lumina_cache"
    raw_hash = get_cache_hash(filename)
    if is_wasm:
        raw_hash += "_wasm"
    if is_debug:
        raw_hash += "_debug"
    if is_no_gc:
        raw_hash += "_nogc"
    if target_triple:
        raw_hash += "_" + target_triple.replace("-", "_").replace(".", "_")
    cache_file = os.path.join(cache_dir, raw_hash + ".ll") if use_cache else None

    if use_cache and os.path.exists(cache_file):
        info("⚡ Usando cache de compilação (.lumina_cache)...")
        with open(cache_file, "r") as f:
            llvm_ir = f.read()
        with open(output_file, "w") as f:
            f.write(llvm_ir)
        return llvm_ir

    header("1. Análise Léxica e Sintática")
    try:
        ast = parse_module(filename)
    except LuminaError as e:
        if on_error:
            on_error(e)
        else:
            error(e)
        return None

    header("2. Análise Semântica")
    with open(filename, "r") as f:
        source_code = f.read()
    analyzer = SemanticAnalyzer(filename, source_code)
    try:
        analyzer.analyze(ast)
    except LuminaError as e:
        if on_error:
            on_error(e)
        else:
            error(e)
        return None

    header("3. Geração de Código LLVM IR")
    codegen = LLVMCodegen(target_triple=target_triple, use_gc=not is_no_gc)
    codegen.escapes = analyzer.escapes
    codegen.freed_vars = getattr(analyzer, 'freed_vars', set())
    codegen.is_wasm = is_wasm
    codegen.is_debug = is_debug
    llvm_ir = codegen.generate_module(ast)

    if not is_debug:
        header("3b. Otimização LLVM (O1)")
        # Otimiza o IR antes de salvar. Para --release, o build.py ainda
        # roda o `opt -O2` externo posteriormente para máxima performance.
        llvm_ir = _optimize_ir(llvm_ir, opt_level=1)

    with open(output_file, "w") as f:
        f.write(llvm_ir)

    if use_cache:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_file, "w") as f:
            f.write(llvm_ir)

    return llvm_ir


def check_lumina(filename, on_error=None):
    """Roda apenas lexer + parser + semantic. Sem codegen.

    Retorna True se o arquivo está OK, False se há erros.
    """
    header("1. Análise Léxica e Sintática")
    try:
        ast = parse_module(filename)
    except LuminaError as e:
        if on_error:
            on_error(e)
        else:
            error(e)
        return False

    header("2. Análise Semântica")
    try:
        with open(filename, "r") as f:
            source_code = f.read()
    except Exception:
        source_code = ""

    analyzer = SemanticAnalyzer(filename, source_code)
    try:
        analyzer.analyze(ast)
    except LuminaError as e:
        if on_error:
            on_error(e)
        else:
            error(e)
        return False

    return True


def run_jit(llvm_ir, cli_args):
    """Roda o IR via JIT. Retorna o exit code da função main()."""
    header("Execução JIT (Just-In-Time)")
    try:
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()
    except Exception:
        pass

    lib_c_path = ctypes.util.find_library('c')
    if lib_c_path:
        llvm.load_library_permanently(lib_c_path)

    mod = llvm.parse_assembly(llvm_ir)
    mod.verify()
    target = llvm.Target.from_default_triple()
    tm = target.create_target_machine()
    engine = llvm.create_mcjit_compiler(mod, tm)
    engine.finalize_object()
    engine.run_static_constructors()

    func_ptr = engine.get_function_address("main")
    cfunc = ctypes.CFUNCTYPE(
        ctypes.c_int, ctypes.c_int32, ctypes.POINTER(ctypes.c_char_p)
    )(func_ptr)

    full_args = ["lumina_program"] + list(cli_args or [])
    argc = len(full_args)
    argv = [arg.encode('utf-8') for arg in full_args]

    info("Executando...\n")
    ret = cfunc(argc, (ctypes.c_char_p * len(argv))(*argv))
    ctypes.CDLL(None).fflush(None)
    print()
    info(f"[JIT] Programa finalizado com exit code: "
         f"{paint(str(ret), Color.BOLD + Color.SUCCESS)}")
    return ret