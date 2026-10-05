"""Fluxo `lumina new` → `build` → `run`."""
import os
import subprocess
import textwrap


def test_new_and_build(tmp_path, run_cli):
    proj_name = "meu_teste_proj"
    result = run_cli("new", proj_name, cwd=tmp_path)
    assert result.returncode == 0, f"Erro em 'lumina new': {result.stderr}"

    proj_dir = os.path.join(tmp_path, proj_name)
    assert os.path.exists(os.path.join(proj_dir, "main.lm"))
    assert os.path.exists(os.path.join(proj_dir, "lumina.toml"))

    result = run_cli("build", cwd=proj_dir)
    assert result.returncode == 0, f"Erro em 'lumina build': {result.stderr}"
    assert "Build concluído" in result.stdout

    binary_path = os.path.join(proj_dir, proj_name)
    assert os.path.exists(binary_path), "Binário nativo não encontrado"

    proc = subprocess.run([binary_path], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "Hello from meu_teste_proj!" in proc.stdout


def test_extra_objects_honors_extra_flags(tmp_path, run_cli):
    """`extra_flags` do lumina.toml devem ser repassadas ao compilar .cpp.

    Sem o fix, o .cpp era compilado sem `-DFOO=42`, e o valor de
    `foo_value()` seria 0 em vez de 42.
    """
    # 1. Cria projeto
    proj = tmp_path / "flag_test"
    run_cli("new", "flag_test", cwd=tmp_path)

    # 2. helper.cpp que retorna FOO (define passada por -D)
    (proj / "helper.cpp").write_text(textwrap.dedent("""
        extern "C" int foo_value() {
        #ifdef FOO
            return FOO;
        #else
            return 0;
        #endif
        }
    """))

    # 3. lumina.toml com extra_objects E extra_flags
    (proj / "lumina.toml").write_text(textwrap.dedent("""
        [package]
        name = "flag_test"
        version = "0.1.0"
        entry = "main.lm"

        [link]
        extra_objects = ["helper.cpp"]
        extra_flags = ["-DFOO=42"]
    """))

    # 4. main.lm que chama foo_value
    (proj / "main.lm").write_text(textwrap.dedent("""
        extern fn foo_value() -> int

        fn main() -> int:
            let v = foo_value()
            print("foo:", v)
            return 0
    """))

    # 5. Build + run
    build = run_cli("build", cwd=proj)
    assert build.returncode == 0, (
        f"Build falhou:\n{build.stdout}\n{build.stderr}"
    )

    binary = proj / "flag_test"
    proc = subprocess.run([str(binary)], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "foo: 42" in proc.stdout, (
        f"extra_flags (-DFOO=42) não foi aplicada ao .cpp:\n{proc.stdout}"
    )