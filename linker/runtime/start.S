/* linker/runtime/start.S — _start x86_64 Linux
 * Compilar: clang -c runtime/start.S -o runtime/start.o
 */
    .text
    .globl _start
    .type  _start, @function
_start:
    xor  %rbp, %rbp            /* frame limpo para o backtrace */
    mov  (%rsp), %rdi          /* argc */
    lea  8(%rsp), %rsi         /* argv */
    and  $-16, %rsp            /* alinha para a chamada (ABI) */
    call main
    mov  %eax, %edi            /* exit code = retorno de main */
    mov  $60, %eax             /* SYS_exit_group */
    syscall
    hlt                        /* nunca chega aqui */
    .size _start, . - _start

    .section .note.GNU-stack,"",@progbits

/* ================= Corrotinas ================= */
/* swapcontext(ucp_save, ucp_activate)
 * rdi = ponteiro para salvar o contexto atual
 * rsi = ponteiro para carregar o novo contexto
 */
    .text
    .globl swapcontext
    .type  swapcontext, @function
swapcontext:
    /* Salva registros callee-saved no contexto antigo (rdi) */
    mov    %rbx, 0x00(%rdi)
    mov    %rbp, 0x08(%rdi)
    mov    %r12, 0x10(%rdi)
    mov    %r13, 0x18(%rdi)
    mov    %r14, 0x20(%rdi)
    mov    %r15, 0x28(%rdi)
    mov    (%rsp), %rax      /* Pega o RIP de retorno */
    mov    %rax, 0x38(%rdi)
    lea    8(%rsp), %rax     /* Calcula o RSP de retorno */
    mov    %rax, 0x30(%rdi)

    /* Carrega novos registros do novo contexto (rsi) */
    mov    0x00(%rsi), %rbx
    mov    0x08(%rsi), %rbp
    mov    0x10(%rsi), %r12
    mov    0x18(%rsi), %r13
    mov    0x20(%rsi), %r14
    mov    0x28(%rsi), %r15
    mov    0x30(%rsi), %rsp
    mov    0x38(%rsi), %rax  /* Novo RIP */
    jmp    *%rax             /* Pula para a nova rotina */
    .size  swapcontext, . - swapcontext

/* ================= getcontext ================= */
/* getcontext(ucp)
 * rdi = ponteiro para salvar o contexto atual
 */
    .text
    .globl getcontext
    .type  getcontext, @function
getcontext:
    /* Salva os registradores callee-saved */
    mov    %rbx, 0x00(%rdi)
    mov    %rbp, 0x08(%rdi)
    mov    %r12, 0x10(%rdi)
    mov    %r13, 0x18(%rdi)
    mov    %r14, 0x20(%rdi)
    mov    %r15, 0x28(%rdi)

    /* Salva o ponteiro de pilha atual (RSP + 8 para ignorar o endereço de retorno) */
    lea    8(%rsp), %rax
    mov    %rax, 0x30(%rdi)

    /* Salva o endereço de retorno atual (RIP) */
    mov    (%rsp), %rax
    mov    %rax, 0x38(%rdi)

    /* Retorna 0 (sucesso) */
    xor    %eax, %eax
    ret
    .size  getcontext, . - getcontext