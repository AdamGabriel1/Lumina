#!/usr/bin/env bash
# scripts/bootstrap_test.sh — alias para bootstrap_ast_test.sh.
#
# A versão antiga validava o output do lexer (print_tokens). Depois
# que o parser.lm passou a fazer dump de AST, o script ficou obsoleto.
# A verificação completa agora vive em bootstrap_ast_test.sh.
exec "$(dirname "$0")/bootstrap_ast_test.sh" "$@"
