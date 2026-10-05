/* linker/runtime/rt.c — runtime freestanding do Lumina
 *
 * Compilar:
 *   clang -c -ffreestanding -fno-pic -fno-pie \
 *         -fno-stack-protector -fno-builtin -nostdlib \
 *         -O2 rt.c -o rt.o
 *
 * IMPORTANTE: este arquivo NÃO define `main`. O `main` é sempre
 * definido pelo `.o` do usuário (compilado do `.lm`). `_start` (em
 * start.S) referencia `main` como UNDEF e resolve contra o objeto
 * do usuário.
 *
 * ----------------------------------------------------------------------
 * Notas de escopo:
 *
 * - `malloc` é thread-safe (spinlock global). `free` continua no-op.
 *
 * - TLS é real (variant II x86_64, via %fs).
 *
 * - pthreads: `pthread_create`/`pthread_join` com assinatura
 *   compatível com a libc (POSIX). `_PThread` é um descritor interno
 *   mapeado por `tid`; o usuário só vê o `pthread_t` opaco
 *   (`unsigned long`).
 * ----------------------------------------------------------------------
 */
typedef unsigned long size_t;
typedef long          ssize_t;

/* ================= forward declarations ================= */
void  *malloc(size_t);
void   free(void*);
void  *calloc(size_t, size_t);
void  *memset(void*, int, size_t);
void  *memcpy(void*, const void*, size_t);
void  *memmove(void*, const void*, size_t);
int    memcmp(const void*, const void*, size_t);
size_t strlen(const char*);
int    strcmp(const char*, const char*);
int    strncmp(const char*, const char*, size_t);
char  *strcpy(char*, const char*);
char  *strncpy(char*, const char*, size_t);
char  *strcat(char*, const char*);
char  *strstr(const char*, const char*);
int    puts(const char*);
long   atoi(const char*);
int    putchar(int);
int    getchar(void);
int    usleep(unsigned int);
int    remove(const char*);
int    printf(const char*, ...);
int    snprintf(char*, size_t, const char*, ...);
void   abort(void);
void  *fopen(const char*, const char*);
int    fclose(void*);
size_t fread(void*, size_t, size_t, void*);
size_t fwrite(const void*, size_t, size_t, void*);
int    fseek(void*, long, int);
long   ftell(void*);
char  *fgets(char*, int, void*);
int    fputs(const char*, void*);
int    fflush(void*);
double pow(double, double);
double sqrt(double);
double floor(double);
double ceil(double);
double round(double);
int    abs(int);
long   labs(long);
int    rand(void);
void   srand(unsigned int);
int    open(const char*, int, ...);
int    close(int);
long   read(int, void*, size_t);
long   write(int, const void*, size_t);
long   lseek(int, long, int);
void   GC_init(void);
void  *GC_malloc(size_t);
void   GC_free(void*);
void   makecontext(void *ucp, void (*func)(), void *stack, size_t stack_size);
int    swapcontext(void *oucp, const void *ucp);

/* TLS API */
void         _lumina_tls_init(void);
void        *_lumina_get_tls(void);
void         _lumina_set_tls(void *ptr);
void        *_lumina_tls_alloc_child(void);
unsigned int _lumina_tls_key_create(void (*destructor)(void *));
int          _lumina_tls_key_delete(unsigned int k);
void        *_lumina_tls_get(unsigned int k);
int          _lumina_tls_set(unsigned int k, void *v);
void         _lumina_tls_run_destructors(void);

/* pthreads (assinatura libc) */
typedef unsigned long pthread_t;
int pthread_create(pthread_t *thread, const void *attr,
                   void *(*start_routine)(void *), void *arg);
int pthread_join(pthread_t thread, void **retval);
int pthread_mutex_init(void *m, const void *attr);
int pthread_mutex_lock(void *m);
int pthread_mutex_unlock(void *m);
int pthread_cond_init(void *c, const void *attr);
int pthread_cond_wait(void *c, void *m);
int pthread_cond_signal(void *c);

/* ================= syscalls Linux x86_64 ================= */
static long _sys1(long n, long a) {
    long r;
    __asm__ volatile("syscall" : "=a"(r) : "a"(n), "D"(a) : "rcx", "r11", "memory");
    return r;
}
static long _sys2(long n, long a, long b) {
    long r;
    __asm__ volatile("syscall" : "=a"(r) : "a"(n), "D"(a), "S"(b) : "rcx", "r11", "memory");
    return r;
}
static long _sys3(long n, long a, long b, long c) {
    long r;
    __asm__ volatile("syscall" : "=a"(r) : "a"(n), "D"(a), "S"(b), "d"(c) : "rcx", "r11", "memory");
    return r;
}
static long _sys4(long n, long a, long b, long c, long d) {
    long r;
    register long r10 __asm__("r10") = d;
    __asm__ volatile("syscall" : "=a"(r) : "a"(n), "D"(a), "S"(b), "d"(c), "r"(r10) : "rcx", "r11", "memory");
    return r;
}
static long _sys5(long n, long a, long b, long c, long d, long e) {
    long r;
    register long r10 __asm__("r10") = d;
    register long r8  __asm__("r8")  = e;
    __asm__ volatile("syscall" : "=a"(r) : "a"(n), "D"(a), "S"(b), "d"(c), "r"(r10), "r"(r8) : "rcx", "r11", "memory");
    return r;
}
static long _sys6(long n, long a, long b, long c, long d, long e, long f) {
    long r;
    register long r10 __asm__("r10") = d;
    register long r8  __asm__("r8")  = e;
    register long r9  __asm__("r9")  = f;
    __asm__ volatile("syscall" : "=a"(r) : "a"(n), "D"(a), "S"(b), "d"(c), "r"(r10), "r"(r8), "r"(r9) : "rcx", "r11", "memory");
    return r;
}

static void _write_fd(int fd, const void *buf, size_t n) { _sys3(1, fd, (long)buf, (long)n); }
static void _exit(int code) { _sys1(60, code); __builtin_unreachable(); }

/* ================= memória (brk) + spinlock ================= */
extern char _end;
static char *_heap = 0;
static volatile int _malloc_lock = 0;

typedef struct _GCBlock {
    size_t size;
    int marked;
    struct _GCBlock *next;
} _GCBlock;

static _GCBlock *gc_head = 0;

static inline void _lock(void) {
    while (__atomic_exchange_n(&_malloc_lock, 1, __ATOMIC_ACQUIRE)) {
        while (__atomic_load_n(&_malloc_lock, __ATOMIC_RELAXED)) {}
    }
}
static inline void _unlock(void) {
    __atomic_store_n(&_malloc_lock, 0, __ATOMIC_RELEASE);
}

void GC_init(void) { gc_head = 0; }

void *malloc(size_t n) {
    _lock();
    if (!_heap) _heap = (char*)(((unsigned long)&_end + 4095) & ~4095UL);

    size_t total = sizeof(_GCBlock) + ((n + 15) & ~15UL);
    _GCBlock *b = (_GCBlock *)_heap;
    _heap += total;
    _sys1(12, (long)_heap); /* brk */

    b->size = n;
    b->marked = 0;
    b->next = gc_head;
    gc_head = b;

    void *result = (void*)((char*)b + sizeof(_GCBlock));
    _unlock();
    return result;
}

/* NO-OP por design: sem bookkeeping de blocos vivos, `free` não
 * pode devolver memória sem risco de double-free/use-after-free.
 * Para churn controlado sob --linker=self, use std/alloc.lm (arena).
 * Sob clang (linker padrão), free resolve para glibc. */
void free(void *p) { (void)p; }

void *calloc(size_t n, size_t sz) {
    size_t total = n * sz;
    void *p = malloc(total);
    if (p) memset(p, 0, total);
    return p;
}

void *GC_malloc(size_t n) { return malloc(n); }
void  GC_free(void *p)    { free(p); }


/* ================= TLS (variant II x86_64) ================= */
#define ARCH_SET_FS        0x1002
#define ARCH_GET_FS        0x1003

#define CLONE_VM                0x00000100
#define CLONE_FS                0x00000200
#define CLONE_FILES             0x00000400
#define CLONE_SIGHAND           0x00000800
#define CLONE_SYSVSEM           0x00040000
#define CLONE_THREAD            0x00010000
#define CLONE_SETTLS            0x00080000
#define CLONE_PARENT_SETTID     0x00100000
#define CLONE_CHILD_CLEARTID    0x00200000

#define FUTEX_WAIT              0
#define FUTEX_WAKE              1

#define LUMINA_TLS_STATIC_SIZE  4096
#define LUMINA_TLS_MAX_KEYS     64

typedef struct _TCB {
    void   *self;
    void   *dtv;
    size_t  static_size;
    void  (*entry)(void *);
    void   *entry_arg;
    int     tid;
    int     _pad;
} _TCB;

typedef struct { int in_use; void *value; } _TLSSlot;
typedef struct { _TLSSlot slots[LUMINA_TLS_MAX_KEYS]; } _TLSDtv;

static int    _tls_key_used[LUMINA_TLS_MAX_KEYS];
static void (*_tls_key_dtor[LUMINA_TLS_MAX_KEYS])(void *);

static unsigned char _tls_master_image[LUMINA_TLS_STATIC_SIZE]
    __attribute__((aligned(64), unused));

void *__lumina_tls_block = (void *)0;

static long _arch_prctl(int code, unsigned long addr) {
    return _sys2(158, (long)code, (long)addr);
}

static inline _TCB *_tcb_current(void) {
    unsigned long fs = 0;
    _arch_prctl(ARCH_GET_FS, (unsigned long)&fs);
    return (_TCB *)fs;
}

static _TCB *_tls_alloc_block(void) {
    size_t total = LUMINA_TLS_STATIC_SIZE + sizeof(_TCB);
    long addr = _sys6(9, 0, (long)total, 3, 0x22, -1, 0);
    if (addr < 0) return 0;
    unsigned char *block = (unsigned char *)addr;
    memcpy(block, _tls_master_image, LUMINA_TLS_STATIC_SIZE);

    _TCB *tcb = (_TCB *)(block + LUMINA_TLS_STATIC_SIZE);
    tcb->self        = tcb;
    tcb->dtv         = 0;
    tcb->static_size = LUMINA_TLS_STATIC_SIZE;
    tcb->entry       = 0;
    tcb->entry_arg   = 0;
    tcb->tid         = 0;
    return tcb;
}

static _TLSDtv *_tls_dtv_get(_TCB *tcb) {
    if (!tcb) return 0;
    if (!tcb->dtv) {
        long addr = _sys6(9, 0, (long)sizeof(_TLSDtv), 3, 0x22, -1, 0);
        if (addr < 0) return 0;
        tcb->dtv = (void *)addr;
        memset(tcb->dtv, 0, sizeof(_TLSDtv));
    }
    return (_TLSDtv *)tcb->dtv;
}

void _lumina_tls_init(void) {
    _TCB *cur = _tcb_current();
    if (cur) return;
    _TCB *tcb = _tls_alloc_block();
    if (!tcb) return;
    _arch_prctl(ARCH_SET_FS, (unsigned long)tcb);
}

void *_lumina_get_tls(void) { return (void *)_tcb_current(); }
void  _lumina_set_tls(void *ptr) { _arch_prctl(ARCH_SET_FS, (unsigned long)ptr); }
void *_lumina_tls_alloc_child(void) { return (void *)_tls_alloc_block(); }

unsigned int _lumina_tls_key_create(void (*destructor)(void *)) {
    for (int i = 0; i < LUMINA_TLS_MAX_KEYS; i++) {
        if (!_tls_key_used[i]) {
            _tls_key_used[i] = 1;
            _tls_key_dtor[i] = destructor;
            return (unsigned int)i;
        }
    }
    return (unsigned int)-1;
}

int _lumina_tls_key_delete(unsigned int k) {
    if (k >= LUMINA_TLS_MAX_KEYS) return -1;
    _tls_key_used[k] = 0;
    _tls_key_dtor[k] = 0;
    return 0;
}

void *_lumina_tls_get(unsigned int k) {
    if (k >= LUMINA_TLS_MAX_KEYS) return 0;
    _TCB *tcb = _tcb_current();
    if (!tcb) return 0;
    _TLSDtv *dtv = (_TLSDtv *)tcb->dtv;
    if (!dtv || !dtv->slots[k].in_use) return 0;
    return dtv->slots[k].value;
}

int _lumina_tls_set(unsigned int k, void *v) {
    if (k >= LUMINA_TLS_MAX_KEYS) return -1;
    _TCB *tcb = _tcb_current();
    if (!tcb) {
        _lumina_tls_init();
        tcb = _tcb_current();
        if (!tcb) return -1;
    }
    _TLSDtv *dtv = _tls_dtv_get(tcb);
    if (!dtv) return -1;
    dtv->slots[k].in_use = 1;
    dtv->slots[k].value  = v;
    return 0;
}

void _lumina_tls_run_destructors(void) {
    _TCB *tcb = _tcb_current();
    if (!tcb) return;
    _TLSDtv *dtv = (_TLSDtv *)tcb->dtv;
    if (!dtv) return;
    for (int round = 0; round < 4; round++) {
        int any = 0;
        for (unsigned int i = 0; i < LUMINA_TLS_MAX_KEYS; i++) {
            if (dtv->slots[i].in_use && dtv->slots[i].value && _tls_key_dtor[i]) {
                void *v = dtv->slots[i].value;
                dtv->slots[i].value  = 0;
                dtv->slots[i].in_use = 0;
                _tls_key_dtor[i](v);
                any = 1;
            }
        }
        if (!any) break;
    }
}


/* ================= futex ================= */
static int _futex_wait(volatile int *addr, int expected) {
    return (int)_sys6(202, (long)addr, FUTEX_WAIT, (long)expected, 0, 0, 0);
}
static int _futex_wake(volatile int *addr, int n) {
    return (int)_sys6(202, (long)addr, FUTEX_WAKE, (long)n, 0, 0, 0);
}


/* ================= clone() simples (spawn-and-forget) ================= */
int clone(int (*fn)(void*), void *stack, int flags, void *arg) {
    if (!fn || !stack) return -1;

    _TCB *child = _tls_alloc_block();
    if (!child) return -1;
    child->entry     = (void (*)(void *))fn;
    child->entry_arg = arg;

    unsigned long *sp = (unsigned long *)((unsigned long)stack & ~15UL);
    sp -= 2;
    sp[0] = (unsigned long)arg;
    sp[1] = (unsigned long)fn;

    unsigned long clone_flags = (unsigned long)flags | CLONE_SETTLS;

    long r;
    register long r10 __asm__("r10") = 0;
    register long r8  __asm__("r8")  = (long)child;
    __asm__ volatile(
        "syscall\n\t"
        "testq %%rax, %%rax\n\t"
        "jnz 1f\n\t"
        "popq %%rdi\n\t"
        "popq %%rax\n\t"
        "callq *%%rax\n\t"
        "movq %%rax, %%rbx\n\t"
        "callq _lumina_tls_run_destructors\n\t"
        "movq %%rbx, %%rdi\n\t"
        "movq $60, %%rax\n\t"
        "syscall\n\t"
        "1:\n\t"
        : "=a"(r)
        : "0"((long)56),
          "D"(clone_flags),
          "S"(sp),
          "d"(0L),
          "r"(r10),
          "r"(r8)
        : "rcx", "r11", "rbx", "memory"
    );
    return r < 0 ? -1 : (int)r;
}


/* ================= pthreads (libc-compatible) =================
 *
 * pthread_t = unsigned long (tid do kernel).
 *
 * `_PThread` é um descritor interno — o usuário nunca vê.
 * O tid é mapeado em `_pthread_table[]` para o join.
 *
 * `pthread_create`:
 *   1. Aloca `_PThread`.
 *   2. Aloca stack (mmap).
 *   3. Aloca TCB via _tls_alloc_block().
 *   4. clone(CLONE_THREAD|CLONE_SETTLS|CLONE_CHILD_CLEARTID|...)
 *   5. Registra tid → _PThread.
 *
 * `pthread_join`:
 *   1. Lookup tid → _PThread.
 *   2. futex_wait(&done, 1) até kernel zerar (CLONE_CHILD_CLEARTID).
 *   3. munmap stack; remove da tabela; retorna retval.
 */
#define MAX_PTHREADS 256

typedef struct _PThread {
    int            tid;
    void *        (*fn)(void *);
    void          *arg;
    void          *retval;
    volatile int   done;          /* ctid: kernel zera em exit */
    void          *stack;
    size_t         stack_size;
} _PThread;

static _PThread *_pthread_table[MAX_PTHREADS];
static volatile int _pthread_table_lock = 0;

static void _pthread_register(int tid, _PThread *t) {
    while (__atomic_exchange_n(&_pthread_table_lock, 1, __ATOMIC_ACQUIRE)) {}
    for (int i = 0; i < MAX_PTHREADS; i++) {
        if (_pthread_table[i] == 0) {
            _pthread_table[i] = t;
            break;
        }
    }
    __atomic_store_n(&_pthread_table_lock, 0, __ATOMIC_RELEASE);
}

static _PThread *_pthread_lookup_remove(int tid) {
    _PThread *found = 0;
    while (__atomic_exchange_n(&_pthread_table_lock, 1, __ATOMIC_ACQUIRE)) {}
    for (int i = 0; i < MAX_PTHREADS; i++) {
        if (_pthread_table[i] && _pthread_table[i]->tid == tid) {
            found = _pthread_table[i];
            _pthread_table[i] = 0;
            break;
        }
    }
    __atomic_store_n(&_pthread_table_lock, 0, __ATOMIC_RELEASE);
    return found;
}

static void _pthread_trampoline(void *ptr);

static long _clone_pthread(void *stack, int flags, void *tls,
                           int *ptid, int *ctid) {
    long r;
    register long r10 __asm__("r10") = (long)ctid;
    register long r8  __asm__("r8")  = (long)tls;
    __asm__ volatile(
        "syscall\n\t"
        "testq %%rax, %%rax\n\t"
        "jnz 1f\n\t"
        /* child path */
        "popq %%rdi\n\t"            /* ptr -> _PThread */
        "popq %%rax\n\t"            /* trampoline */
        "callq *%%rax\n\t"
        /* defesa: se trampoline retornar, mata a thread */
        "xorl %%edi, %%edi\n\t"
        "movq $60, %%rax\n\t"
        "syscall\n\t"
        /* parent path */
        "1:\n\t"
        : "=a"(r)
        : "0"((long)56),
          "D"((long)flags),
          "S"((long)stack),
          "d"((long)ptid),
          "r"(r10),
          "r"(r8)
        : "rcx", "r11", "memory"
    );
    return r;
}

static void _pthread_trampoline(void *ptr) {
    _PThread *t = (_PThread *)ptr;
    void *ret = t->fn(t->arg);
    t->retval = ret;
    _lumina_tls_run_destructors();
    /* Termina a thread. Em CLONE_THREAD, `exit` (60) só mata a
     * thread atual; o kernel zera *ctid (= t->done) e acorda
     * futexes — o que libera o pthread_join. */
    _exit(0);
}

int pthread_create(pthread_t *thread, const void *attr,
                   void *(*start_routine)(void *), void *arg) {
    (void)attr;
    if (!thread || !start_routine) return -1;

    _PThread *t = (_PThread *)calloc(1, sizeof(_PThread));
    if (!t) return -1;
    t->fn = start_routine;
    t->arg = arg;
    t->done = 1;    /* kernel vai zerar em exit */

    const size_t STACK_SIZE = 64 * 1024;
    long stack_addr = _sys6(9, 0, (long)STACK_SIZE, 3, 0x22, -1, 0);
    if (stack_addr < 0) { free(t); return -1; }
    t->stack = (void *)stack_addr;
    t->stack_size = STACK_SIZE;

    unsigned long *sp = (unsigned long *)
        ((unsigned long)(stack_addr + STACK_SIZE) & ~15UL);
    sp -= 2;
    sp[0] = (unsigned long)t;
    sp[1] = (unsigned long)_pthread_trampoline;

    _TCB *tls = _tls_alloc_block();
    if (!tls) {
        _sys2(11, stack_addr, (long)STACK_SIZE);
        free(t);
        return -1;
    }

    int flags = CLONE_VM | CLONE_FS | CLONE_FILES | CLONE_SIGHAND
              | CLONE_SYSVSEM | CLONE_THREAD | CLONE_SETTLS
              | CLONE_PARENT_SETTID | CLONE_CHILD_CLEARTID;

    int ptid_scratch = 0;
    long tid = _clone_pthread(sp, flags, tls,
                              &ptid_scratch, (int *)&t->done);
    if (tid < 0) {
        _sys2(11, stack_addr, (long)STACK_SIZE);
        free(t);
        return -1;
    }

    t->tid = (int)tid;
    *thread = (pthread_t)tid;
    _pthread_register((int)tid, t);
    return 0;
}

int pthread_join(pthread_t thread, void **retval) {
    _PThread *t = _pthread_lookup_remove((int)thread);
    if (!t) return -1;

    /* Espera `done` virar 0. O kernel faz isso em exit via
     * CLONE_CHILD_CLEARTID e acorda futexes com FUTEX_WAKE. */
    while (__atomic_load_n(&t->done, __ATOMIC_ACQUIRE) != 0) {
        _futex_wait((volatile int *)&t->done, 1);
    }

    if (retval) *retval = t->retval;
    _sys2(11, (long)t->stack, (long)t->stack_size);
    free(t);
    return 0;
}

/* --- mutex futex-based --- */
int pthread_mutex_init(void *m, const void *attr) {
    (void)attr;
    if (!m) return -1;
    *(volatile int *)m = 0;
    return 0;
}
int pthread_mutex_lock(void *m) {
    if (!m) return -1;
    volatile int *s = (volatile int *)m;
    if (__atomic_exchange_n(s, 1, __ATOMIC_ACQUIRE) == 0) return 0;
    while (__atomic_exchange_n(s, 2, __ATOMIC_ACQUIRE) != 0) {
        _futex_wait(s, 2);
    }
    return 0;
}
int pthread_mutex_unlock(void *m) {
    if (!m) return -1;
    volatile int *s = (volatile int *)m;
    if (__atomic_exchange_n(s, 0, __ATOMIC_RELEASE) == 2) {
        _futex_wake(s, 1);
    }
    return 0;
}

/* --- cond seq-counter futex-based --- */
int pthread_cond_init(void *c, const void *attr) {
    (void)attr;
    if (!c) return -1;
    *(volatile int *)c = 0;
    return 0;
}
int pthread_cond_wait(void *c, void *m) {
    if (!c || !m) return -1;
    volatile int *seq = (volatile int *)c;
    int s = __atomic_load_n(seq, __ATOMIC_ACQUIRE);
    pthread_mutex_unlock(m);
    _futex_wait(seq, s);
    pthread_mutex_lock(m);
    return 0;
}
int pthread_cond_signal(void *c) {
    if (!c) return -1;
    volatile int *seq = (volatile int *)c;
    __atomic_add_fetch(seq, 1, __ATOMIC_RELEASE);
    _futex_wake(seq, 1);
    return 0;
}


/* ================= corrotinas ================= */
void makecontext(void *ucp, void (*func)(), void *stack, size_t stack_size) {
    unsigned long *sp = (unsigned long *)((unsigned char *)stack + stack_size);
    sp = (unsigned long *)((unsigned long)sp & ~0xFFUL);
    sp -= 1;

    unsigned long *ctx = (unsigned long *)ucp;
    ctx[6] = (unsigned long)sp;
    ctx[7] = (unsigned long)func;
}


/* ================= mem* ================= */
void *memset(void *d, int c, size_t n) {
    unsigned char *p = (unsigned char*)d;
    while (n--) *p++ = (unsigned char)c;
    return d;
}
void *memcpy(void *d, const void *s, size_t n) {
    unsigned char *dp = (unsigned char*)d;
    const unsigned char *sp = (const unsigned char*)s;
    while (n--) *dp++ = *sp++;
    return d;
}
void *memmove(void *d, const void *s, size_t n) {
    unsigned char *dp = (unsigned char*)d;
    const unsigned char *sp = (const unsigned char*)s;
    if (dp < sp) {
        while (n--) *dp++ = *sp++;
    } else {
        dp += n; sp += n;
        while (n--) *--dp = *--sp;
    }
    return d;
}
int memcmp(const void *a, const void *b, size_t n) {
    const unsigned char *pa = a, *pb = b;
    while (n--) {
        if (*pa != *pb) return (int)*pa - (int)*pb;
        pa++; pb++;
    }
    return 0;
}

/* ================= strings ================= */
size_t strlen(const char *s) {
    size_t n = 0;
    while (s[n]) n++;
    return n;
}
int strcmp(const char *a, const char *b) {
    while (*a && *a == *b) { a++; b++; }
    return (unsigned char)*a - (unsigned char)*b;
}
int strncmp(const char *a, const char *b, size_t n) {
    while (n && *a && *a == *b) { a++; b++; n--; }
    return n ? ((unsigned char)*a - (unsigned char)*b) : 0;
}
char *strcpy(char *d, const char *s) {
    char *o = d;
    do { *d++ = *s; } while (*s++);
    return o;
}
char *strncpy(char *d, const char *s, size_t n) {
    char *o = d;
    while (n && (*d = *s)) { d++; s++; n--; }
    while (n--) *d++ = 0;
    return o;
}
char *strcat(char *d, const char *s) {
    char *o = d;
    while (*d) d++;
    do { *d++ = *s; } while (*s++);
    return o;
}
int puts(const char *s) {
    size_t n = strlen(s);
    _write_fd(1, s, n);
    _write_fd(1, "\n", 1);
    return (int)(n + 1);
}
char *strstr(const char *h, const char *n) {
    if (!*n) return (char*)h;
    for (; *h; h++) {
        const char *a = h, *b = n;
        while (*a && *b && *a == *b) { a++; b++; }
        if (!*b) return (char*)h;
    }
    return 0;
}
long atoi(const char *s) {
    long v = 0;
    int neg = 0;
    while (*s == ' ' || *s == '\t') s++;
    if (*s == '-') { neg = 1; s++; }
    else if (*s == '+') s++;
    while (*s >= '0' && *s <= '9') v = v * 10 + (*s++ - '0');
    return neg ? -v : v;
}

/* ================= putchar / getchar ================= */
int putchar(int c) {
    unsigned char ch = (unsigned char)c;
    _write_fd(1, &ch, 1);
    return c;
}
int getchar(void) {
    char c;
    long r = _sys3(0, 0, (long)&c, 1);
    return r > 0 ? (unsigned char)c : -1;
}

/* ================= usleep ================= */
int usleep(unsigned int usec) {
    struct { long tv_sec; long tv_nsec; } ts;
    ts.tv_sec  = usec / 1000000UL;
    ts.tv_nsec = (long)(usec % 1000000UL) * 1000L;
    return (int)_sys2(35, (long)&ts, 0);
}

/* ================= remove ================= */
int remove(const char *path) {
    long r = _sys1(87, (long)path);
    return r < 0 ? -1 : 0;
}

/* ================= math ================= */
int abs(int x) { return x < 0 ? -x : x; }
long labs(long x) { return x < 0 ? -x : x; }
double floor(double x) { long i = (long)x; return (x < 0.0 && x != (double)i) ? (double)(i - 1) : (double)i; }
double ceil(double x) { long i = (long)x; return (x > 0.0 && x != (double)i) ? (double)(i + 1) : (double)i; }
double round(double x) { return (x >= 0.0) ? (double)(long)(x + 0.5) : (double)(long)(x - 0.5); }
double sqrt(double x) {
    if (x <= 0.0) return 0.0;
    double r = x;
    for (int i = 0; i < 30; i++) r = 0.5 * (r + x / r);
    return r;
}
double pow(double base, double exp) {
    if (exp == 0.0) return 1.0;
    if (exp == 1.0) return base;
    if (exp == 2.0) return base * base;
    if (exp == 0.5) return sqrt(base);

    int neg = 0;
    if (exp < 0.0) { neg = 1; exp = -exp; }
    long ie = (long)exp;
    if ((double)ie == exp) {
        double r = 1.0, b = base;
        while (ie > 0) { if (ie & 1) r *= b; b *= b; ie >>= 1; }
        return neg ? 1.0 / r : r;
    }
    if (base <= 0.0) return 0.0;
    double m = base, k = 0.0;
    while (m > 2.0) { m *= 0.5; k += 1.0; }
    while (m < 0.5) { m *= 2.0; k -= 1.0; }
    double z = (m - 1.0) / (m + 1.0);
    double z2 = z * z, term = z, ln = 0.0;
    for (int i = 0; i < 30; i++) { ln += term / (2.0 * i + 1.0); term *= z2; }
    ln *= 2.0; ln += k * 0.69314718055994530942;

    double r = 1.0, b = base;
    long n = (long)exp;
    while (n > 0) { if (n & 1) r *= b; b *= b; n >>= 1; }
    double frac = exp - (double)(long)exp;
    r *= 1.0 + frac * ln;
    return neg ? 1.0 / r : r;
}

/* ================= rand / srand ================= */
static unsigned long _rand_seed = 1;
void srand(unsigned int seed) { _rand_seed = seed; }
int rand(void) { _rand_seed = (_rand_seed * 1103515245UL + 12345UL) & 0x7fffffffUL; return (int)_rand_seed; }

/* ================= I/O por fd ================= */
int open(const char *path, int flags, ...) { return (int)_sys3(2, (long)path, flags, 0644); }
int close(int fd) { return (int)_sys1(3, fd); }
long read(int fd, void *buf, size_t n) { return _sys3(0, fd, (long)buf, (long)n); }
long write(int fd, const void *buf, size_t n) { return _sys3(1, fd, (long)buf, (long)n); }
long lseek(int fd, long off, int whence) { return _sys3(8, fd, off, whence); }

/* ================= printf / snprintf ================= */
static int _format_to(char *dst, size_t cap, const char *fmt, __builtin_va_list ap) {
    size_t i = 0;
    #define PUT(c) do { if (i < cap - 1) dst[i] = (c); i++; } while (0)

    for (const char *p = fmt; *p; p++) {
        if (*p != '%') { PUT(*p); continue; }
        p++;
        switch (*p) {
        case 's': {
            const char *s = __builtin_va_arg(ap, const char*);
            if (!s) s = "(null)";
            while (*s) PUT(*s++);
            break;
        }
        case 'c': {
            int c = __builtin_va_arg(ap, int);
            PUT((char)c);
            break;
        }
        case 'd': {
            int v = __builtin_va_arg(ap, int);
            char tmp[16]; int k = 0;
            unsigned int u = (v < 0) ? (unsigned)(-v) : (unsigned)v;
            if (v < 0) PUT('-');
            if (!u) tmp[k++] = '0';
            while (u) { tmp[k++] = '0' + (u % 10); u /= 10; }
            while (k--) PUT(tmp[k]);
            break;
        }
        case 'l': {
            if (p[1] == 'd') {
                p++;
                long v = __builtin_va_arg(ap, long);
                char tmp[24]; int k = 0;
                unsigned long u = (v < 0) ? (unsigned long)(-v) : (unsigned long)v;
                if (v < 0) PUT('-');
                if (!u) tmp[k++] = '0';
                while (u) { tmp[k++] = '0' + (u % 10); u /= 10; }
                while (k--) PUT(tmp[k]);
            } else if (p[1] == 'u') {
                p++;
                unsigned long u = __builtin_va_arg(ap, unsigned long);
                char tmp[24]; int k = 0;
                if (!u) tmp[k++] = '0';
                while (u) { tmp[k++] = '0' + (u % 10); u /= 10; }
                while (k--) PUT(tmp[k]);
            } else {
                PUT('%'); PUT('l');
            }
            break;
        }
        case 'u': {
            unsigned int u = __builtin_va_arg(ap, unsigned int);
            char tmp[16]; int k = 0;
            if (!u) tmp[k++] = '0';
            while (u) { tmp[k++] = '0' + (u % 10); u /= 10; }
            while (k--) PUT(tmp[k]);
            break;
        }
        case 'x': {
            unsigned int u = __builtin_va_arg(ap, unsigned int);
            char tmp[16]; int k = 0;
            const char *hex = "0123456789abcdef";
            if (!u) tmp[k++] = '0';
            while (u) { tmp[k++] = hex[u & 0xF]; u >>= 4; }
            while (k--) PUT(tmp[k]);
            break;
        }
        case 'p': {
            void *v = __builtin_va_arg(ap, void*);
            unsigned long u = (unsigned long)v;
            char tmp[20]; int k = 0;
            const char *hex = "0123456789abcdef";
            PUT('0'); PUT('x');
            if (!u) tmp[k++] = '0';
            while (u) { tmp[k++] = hex[u & 0xF]; u >>= 4; }
            while (k--) PUT(tmp[k]);
            break;
        }
        case 'f': {
            double v = __builtin_va_arg(ap, double);
            if (v < 0) { PUT('-'); v = -v; }
            long ip = (long)v;
            double fp = v - (double)ip;
            char tmp[24]; int k = 0;
            if (!ip) tmp[k++] = '0';
            while (ip) { tmp[k++] = '0' + (ip % 10); ip /= 10; }
            while (k--) PUT(tmp[k]);
            PUT('.');
            for (int d = 0; d < 6; d++) {
                fp *= 10.0;
                int digit = (int)fp;
                if (digit < 0) digit = 0;
                if (digit > 9) digit = 9;
                PUT('0' + digit);
                fp -= digit;
            }
            break;
        }
        case '%':
            PUT('%');
            break;
        default:
            PUT('%');
            PUT(*p);
            break;
        }
    }
    if (cap) dst[i < cap ? i : cap - 1] = 0;
    #undef PUT
    return (int)i;
}

int printf(const char *fmt, ...) {
    char buf[2048];
    __builtin_va_list ap;
    __builtin_va_start(ap, fmt);
    int n = _format_to(buf, sizeof(buf), fmt, ap);
    __builtin_va_end(ap);
    _write_fd(1, buf, (size_t)(n < (int)sizeof(buf) ? n : (int)sizeof(buf) - 1));
    return n;
}

int snprintf(char *dst, size_t cap, const char *fmt, ...) {
    __builtin_va_list ap;
    __builtin_va_start(ap, fmt);
    int n = _format_to(dst, cap, fmt, ap);
    __builtin_va_end(ap);
    return n;
}

void abort(void) { _exit(134); }

/* ================= FILE* mínimo ================= */
typedef struct { int fd; int eof; int err; } _LFile;
static _LFile _stdin_s  = { 0, 0, 0 };
static _LFile _stdout_s = { 1, 0, 0 };
static _LFile _stderr_s = { 2, 0, 0 };

void *stdin  = &_stdin_s;
void *stdout = &_stdout_s;
void *stderr = &_stderr_s;

void *fopen(const char *path, const char *mode) {
    int flags;
    int m = mode[0];
    if (m == 'r')      flags = 0;
    else if (m == 'w') flags = 1 | 64 | 512;
    else if (m == 'a') flags = 1 | 64 | 1024;
    else               return 0;
    long fd = _sys3(2, (long)path, flags, 0644);
    if (fd < 0) return 0;
    _LFile *f = (_LFile *)malloc(sizeof(_LFile));
    if (!f) { _sys1(3, fd); return 0; }
    f->fd = (int)fd; f->eof = 0; f->err = 0;
    return f;
}

int fclose(void *fp) {
    _LFile *f = (_LFile *)fp;
    if (!f) return -1;
    if (f->fd > 2) _sys1(3, f->fd);
    return 0;
}

size_t fread(void *buf, size_t sz, size_t n, void *fp) {
    _LFile *f = (_LFile *)fp;
    if (!f || !sz || !n) return 0;
    size_t want = sz * n;
    long got = _sys3(0, f->fd, (long)buf, want);
    if (got <= 0) { f->eof = 1; return 0; }
    return (size_t)got / sz;
}

size_t fwrite(const void *buf, size_t sz, size_t n, void *fp) {
    _LFile *f = (_LFile *)fp;
    if (!f || !sz || !n) return 0;
    size_t total = sz * n;
    _write_fd(f->fd, buf, total);
    return n;
}

int fseek(void *fp, long off, int whence) {
    _LFile *f = (_LFile *)fp;
    if (!f) return -1;
    long r = _sys3(8, f->fd, off, whence);
    return r < 0 ? -1 : 0;
}

long ftell(void *fp) {
    _LFile *f = (_LFile *)fp;
    if (!f) return -1;
    return _sys3(8, f->fd, 0, 1);
}

char *fgets(char *buf, int n, void *fp) {
    _LFile *f = (_LFile *)fp;
    if (!f || n <= 0) return 0;
    int i = 0;
    while (i < n - 1) {
        char c;
        long r = _sys3(0, f->fd, (long)&c, 1);
        if (r <= 0) break;
        buf[i++] = c;
        if (c == '\n') break;
    }
    buf[i] = 0;
    if (i == 0) { f->eof = 1; return 0; }
    return buf;
}

int fputs(const char *s, void *fp) {
    _LFile *f = (_LFile *)fp;
    if (!f) return -1;
    size_t n = strlen(s);
    _write_fd(f->fd, s, n);
    return (int)n;
}

int fflush(void *fp) { (void)fp; return 0; }

/* ================= Sockets e Epoll ================= */
int socket(int domain, int type, int protocol) { return (int)_sys3(41, domain, type, protocol); }
int bind(int fd, const void *addr, size_t len) { return (int)_sys3(49, fd, (long)addr, len); }
int listen(int fd, int backlog) { return (int)_sys2(50, fd, backlog); }
int accept(int fd, void *addr, void *addrlen) { return (int)_sys3(43, fd, (long)addr, (long)addrlen); }
int connect(int fd, const void *addr, size_t len) { return (int)_sys3(42, fd, (long)addr, len); }
long send(int fd, const void *buf, size_t n, int flags) { return _sys4(44, fd, (long)buf, n, flags); }
long recv(int fd, void *buf, size_t n, int flags) { return _sys4(45, fd, (long)buf, n, flags); }
int setsockopt(int fd, int level, int optname, const void *optval, size_t optlen) { return (int)_sys5(54, fd, level, optname, (long)optval, optlen); }

int epoll_create1(int flags) { return (int)_sys1(291, flags); }
int epoll_ctl(int epfd, int op, int fd, void *event) { return (int)_sys4(233, epfd, op, fd, (long)event); }
int epoll_wait(int epfd, void *events, int maxevents, int timeout) { return (int)_sys4(232, epfd, (long)events, maxevents, timeout); }


/* ============================================================
 * FIM do arquivo.
 *
 * NÃO adicione `main` aqui. O `main` é definido pelo `.o` do
 * usuário (compilado do `.lm`). `_start` referencia `main` como
 * UNDEF; o linker resolve contra o objeto do usuário.
 * ============================================================ */