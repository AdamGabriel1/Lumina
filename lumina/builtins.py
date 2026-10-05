"""Fonte única de verdade para funções nativas (builtins)."""

BUILTIN_FUNCTIONS = frozenset({
    "print",
    "input",
    "atoi",
    "len",
    "alloc",
    "alloc_bytes",
    "free",
    "read_file",
    "write_file",
    "int",
    "float",
    "str",
    "argv",
    "chr",
    "http_response",
    "black_box",
    "bytes",            # NOVO — str → [int]
    "copy",             # NOVO — [T] → [T]
    # FILE* globals do libc
    "stdin",
    "stdout",
    "stderr",
    # I/O de stream
    "fgets",
    "fputs",
    "fflush",
    "getchar",
})

BUILTIN_RET = {
    "print": "void",
    "input": "str",
    "atoi": "int",
    "len": "int",
    "alloc": "ptr",
    "alloc_bytes": "ptr",
    "free": "void",
    "read_file": "str",
    "write_file": "void",
    "int": "int",
    "float": "float",
    "str": "str",
    "argv": "str",
    "chr": "str",
    "http_response": "str",
    "black_box": "int",
    "bytes": "[int]",   # NOVO
    "copy": "[int]",    # NOVO — placeholder; semantic refina com o tipo do arg
    "stdin": "str",
    "stdout": "str",
    "stderr": "str",
    "fgets": "str",
    "fputs": "int",
    "fflush": "int",
    "getchar": "int",
}