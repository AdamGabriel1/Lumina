/* lumina-ld — linker estático minimalista para Linux x86_64
 *
 * Uso: lumina-ld [-e <sym>] <input.o>... -o <saida>
 *
 * Faz:  parse ELF .o → merge de .text/.rodata/.data/.bss →
 *       resolução de símbolos globais → relocação → EXEC ELF.
 *
 * Escopo: x86_64, ET_REL → ET_EXEC, W^X estrito (2 PT_LOAD).
 * Sem libc, sem .so, sem PLT/GOT real, sem TLS.
 * Suporta SHN_COMMON.
 *
 * Compilar: clang -O2 -Wall -Wextra link.c -o lumina-ld
 *
 * ----------------------------------------------------------------------
 * Histórico de decisões:
 *
 * v0.5.0 — versão inicial: 1 PT_LOAD RWX.
 *
 * v0.5.1 — W^X: 2 PT_LOAD (RX + RW), page-align entre .rodata e .data.
 *
 * v0.5.2 — Preferência de `main` do usuário:
 *          símbolos `main` vindos de runtime (start.o / rt.o) são
 *          filtrados em `build_gsyms`. Garante que o `main` do usuário
 *          sempre vence, mesmo se o runtime emitir um `main` sintético
 *          (bug de assembler, resíduo de build, ou edição acidental).
 * ----------------------------------------------------------------------
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <elf.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/mman.h>

/* Constantes que podem faltar em <elf.h> antigo */
#ifndef R_X86_64_GOTPCREL
#define R_X86_64_GOTPCREL        9
#endif
#ifndef R_X86_64_GOTPCRELX
#define R_X86_64_GOTPCRELX       41
#endif
#ifndef R_X86_64_REX_GOTPCRELX
#define R_X86_64_REX_GOTPCRELX   42
#endif

#define BASE_ADDR      0x400000UL
#define TEXT_OFF       0x1000UL
#define HEAP_FOLGA     0x10000UL   /* 64 KB de folga após _end */
#define N_OUT_SECS     4
#define PAGE_SIZE      0x1000UL

enum { OS_TEXT = 0, OS_RODATA, OS_DATA, OS_BSS };

static void die(const char *m) { perror(m); exit(1); }
static void err(const char *m) { fprintf(stderr, "lumina-ld: %s\n", m); exit(1); }

static uint64_t align_up(uint64_t x, uint64_t a) {
    return a <= 1 ? x : (x + a - 1) & ~(a - 1);
}

typedef struct { int out_sec; uint64_t out_off; } SecMap;

typedef struct {
    const char *path;
    uint8_t    *data;
    size_t      size;
    Elf64_Ehdr *ehdr;
    Elf64_Shdr *shdrs;
    const char *shstrtab;
    Elf64_Sym  *symtab;
    size_t      nsyms;
    const char *strtab;
    SecMap     *map;
} Input;

typedef struct {
    const char *name;
    uint8_t    *data;
    size_t      size, cap;
    uint64_t    align;
    uint64_t    vaddr;
    int         nobits;
} OutSec;

typedef struct { char *name; int in_idx, sym_idx; uint8_t bind; } GSymbol;

static Input   *inputs;
static int      ninputs;
static OutSec   outsecs[N_OUT_SECS];
static GSymbol *gsyms;
static int      ngsyms, cgsyms;
static uint64_t g_file_end, g_mem_end;
static uint64_t g_rx_end;
static const char *entry_sym = "_start";

/* ================= helpers ================= */

static const char *sec_name(Input *in, int i) {
    if (in->shdrs[i].sh_name == 0) return "";
    return in->shstrtab + in->shdrs[i].sh_name;
}

static int find_sec(Input *in, const char *name) {
    for (int i = 0; i < in->ehdr->e_shnum; i++)
        if (!strcmp(sec_name(in, i), name)) return i;
    return -1;
}

static int out_sec_for(const char *name) {
    if (!strcmp(name, ".text")   || !strncmp(name, ".text.",   6)) return OS_TEXT;
    if (!strcmp(name, ".rodata") || !strncmp(name, ".rodata.", 8)) return OS_RODATA;
    if (!strcmp(name, ".data")   || !strncmp(name, ".data.",   6)) return OS_DATA;
    if (!strcmp(name, ".bss")    || !strncmp(name, ".bss.",    5)) return OS_BSS;
    return -1;
}

/* ------------------------------------------------------------------
 * Detecta se um objeto é runtime (start.o / rt.o).
 * Compara só o basename — tolera paths relativos, absolutos, symlinks.
 * ------------------------------------------------------------------ */
static int is_runtime_obj(const char *path) {
    const char *base = strrchr(path, '/');
    base = base ? base + 1 : path;
    return (!strcmp(base, "start.o") || !strcmp(base, "rt.o"));
}

/* ------------------------------------------------------------------
 * Símbolos que NUNCA são aceitos vindos de um objeto de runtime.
 *
 * Hoje, só `main`. Motivo: o runtime NÃO deve definir `main` — quem
 * define é o `.lm` do usuário. Um `main` no runtime é resíduo (bug
 * de assembler, edição acidental, build sujo).
 *
 * Filtrar em `build_gsyms` (em vez de resolver em `add_gsym`) torna
 * o comportamento determinístico e independente da ordem dos inputs
 * na linha de comando.
 * ------------------------------------------------------------------ */
static int is_runtime_sym(const char *name) {
    return !strcmp(name, "main");
}

/* ================= Fase 1: load ================= */

static Input load_input(const char *path) {
    Input in; memset(&in, 0, sizeof in);
    in.path = path;

    int fd = open(path, O_RDONLY);
    if (fd < 0) die(path);
    struct stat st;
    if (fstat(fd, &st) < 0) die("fstat");
    in.size = st.st_size;
    in.data = mmap(NULL, in.size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (in.data == MAP_FAILED) die("mmap");
    close(fd);

    in.ehdr = (Elf64_Ehdr *)in.data;
    if (memcmp(in.ehdr->e_ident, ELFMAG, SELFMAG)) err("não é ELF");
    if (in.ehdr->e_ident[EI_CLASS] != ELFCLASS64) err("precisa 64-bit");
    if (in.ehdr->e_ident[EI_DATA]  != ELFDATA2LSB) err("precisa little-endian");
    if (in.ehdr->e_type    != ET_REL)     err("precisa ser .o (ET_REL)");
    if (in.ehdr->e_machine != EM_X86_64)  err("precisa x86_64");

    in.shdrs    = (Elf64_Shdr *)(in.data + in.ehdr->e_shoff);
    in.shstrtab = (const char *)(in.data + in.shdrs[in.ehdr->e_shstrndx].sh_offset);

    int si  = find_sec(&in, ".symtab");
    int sti = find_sec(&in, ".strtab");
    if (si < 0 || sti < 0) err("faltando .symtab/.strtab");
    in.symtab = (Elf64_Sym *)(in.data + in.shdrs[si].sh_offset);
    in.nsyms  = in.shdrs[si].sh_size / sizeof(Elf64_Sym);
    in.strtab = (const char *)(in.data + in.shdrs[sti].sh_offset);

    in.map = calloc(in.ehdr->e_shnum, sizeof(SecMap));
    if (!in.map) die("calloc");
    for (int i = 0; i < in.ehdr->e_shnum; i++) in.map[i].out_sec = -1;

    return in;
}

/* ================= Fase 3: merge + layout ================= */

static void outsec_reserve(OutSec *s, size_t need) {
    if (need <= s->cap) return;
    size_t nc = s->cap ? s->cap : 4096;
    while (nc < need) nc *= 2;
    s->data = realloc(s->data, nc);
    if (!s->data) die("realloc");
    memset(s->data + s->cap, 0, nc - s->cap);
    s->cap = nc;
}

static void merge_sections(void) {
    static const char *names[N_OUT_SECS] = { ".text", ".rodata", ".data", ".bss" };
    for (int i = 0; i < N_OUT_SECS; i++) {
        outsecs[i].name   = names[i];
        outsecs[i].align  = 16;
        outsecs[i].nobits = (i == OS_BSS);
    }

    for (int f = 0; f < ninputs; f++) {
        Input *in = &inputs[f];
        for (int i = 0; i < in->ehdr->e_shnum; i++) {
            Elf64_Shdr *sh = &in->shdrs[i];
            if (!(sh->sh_flags & SHF_ALLOC)) continue;

            int os = out_sec_for(sec_name(in, i));
            if (os < 0) continue;

            OutSec *o = &outsecs[os];
            uint64_t a = sh->sh_addralign ? sh->sh_addralign : 1;
            if (a > o->align) o->align = a;

            uint64_t old  = o->size;
            uint64_t noff = align_up(old, a);
            size_t   need = (size_t)(noff + sh->sh_size);
            outsec_reserve(o, need);
            if (noff > old) memset(o->data + old, 0, noff - old);
            o->size = need;

            in->map[i].out_sec = os;
            in->map[i].out_off = noff;

            if (sh->sh_type != SHT_NOBITS && sh->sh_size)
                memcpy(o->data + noff, in->data + sh->sh_offset, sh->sh_size);
        }
    }

    uint64_t off = TEXT_OFF, file_end = off;
    g_rx_end = 0;

    for (int i = 0; i < N_OUT_SECS; i++) {
        OutSec *o = &outsecs[i];

        if (i == OS_DATA) {
            off = align_up(off, PAGE_SIZE);
            g_rx_end = off;
        }

        uint64_t a = o->align > 16 ? o->align : 16;
        off = align_up(off, a);
        o->vaddr = BASE_ADDR + off;
        off += o->size;

        if (i != OS_BSS) file_end = off;
    }

    if (g_rx_end == 0) {
        g_rx_end = align_up(file_end, PAGE_SIZE);
    }

    g_file_end = file_end;
    g_mem_end  = off;
}

/* ================= Fase 2: símbolos globais ================= */

static GSymbol *find_gsym(const char *name) {
    for (int i = 0; i < ngsyms; i++)
        if (!strcmp(gsyms[i].name, name)) return &gsyms[i];
    return NULL;
}

static void add_gsym(const char *name, int in_idx, int sym_idx, uint8_t bind) {
    GSymbol *g = find_gsym(name);
    if (g) {
        if (bind == STB_WEAK) return;
        if (g->bind == STB_WEAK) {
            g->in_idx = in_idx; g->sym_idx = sym_idx; g->bind = bind;
            return;
        }
        fprintf(stderr, "lumina-ld: multiple definition of '%s'\n", name);
        exit(1);
    }
    if (ngsyms == cgsyms) {
        cgsyms = cgsyms ? cgsyms * 2 : 128;
        gsyms = realloc(gsyms, cgsyms * sizeof *gsyms);
        if (!gsyms) die("realloc");
    }
    gsyms[ngsyms].name    = strdup(name);
    gsyms[ngsyms].in_idx  = in_idx;
    gsyms[ngsyms].sym_idx = sym_idx;
    gsyms[ngsyms].bind    = bind;
    ngsyms++;
}

static void build_gsyms(void) {
    for (int f = 0; f < ninputs; f++) {
        Input *in = &inputs[f];
        int from_runtime = is_runtime_obj(in->path);

        for (size_t i = 1; i < in->nsyms; i++) {
            Elf64_Sym *s = &in->symtab[i];
            if (s->st_shndx == SHN_UNDEF) continue;
            uint8_t b = ELF64_ST_BIND(s->st_info);
            if (b != STB_GLOBAL && b != STB_WEAK) continue;
            const char *n = in->strtab + s->st_name;
            if (!n[0]) continue;

            /* Filtro: `main` vindo de runtime é descartado. */
            if (from_runtime && is_runtime_sym(n)) {
                continue;
            }

            add_gsym(n, f, (int)i, b);
        }
    }
}

static uint64_t sym_addr(Input *in, int idx) {
    Elf64_Sym  *s    = &in->symtab[idx];
    const char *name = in->strtab + s->st_name;

    if (s->st_shndx == SHN_UNDEF) {
        if (!strcmp(name, "_end") || !strcmp(name, "end"))
            return BASE_ADDR + g_mem_end;
        if (!strcmp(name, "__bss_start"))
            return outsecs[OS_BSS].vaddr;
        if (!strcmp(name, "__bss_end"))
            return outsecs[OS_BSS].vaddr + outsecs[OS_BSS].size;
        if (!strcmp(name, "_edata"))
            return outsecs[OS_DATA].vaddr + outsecs[OS_DATA].size;

        GSymbol *g = find_gsym(name);
        if (!g) {
            if (ELF64_ST_BIND(s->st_info) == STB_WEAK) return 0;
            fprintf(stderr, "lumina-ld: undefined reference to '%s'\n", name);
            exit(1);
        }
        return sym_addr(&inputs[g->in_idx], g->sym_idx);
    }
    if (s->st_shndx == SHN_ABS) return s->st_value;

    if (s->st_shndx == SHN_COMMON) {
        OutSec *bss = &outsecs[OS_BSS];
        uint64_t align = s->st_value ? s->st_value : 1;
        bss->size = align_up(bss->size, align);
        uint64_t addr = bss->vaddr + bss->size;
        bss->size += s->st_size;
        return addr;
    }

    if (s->st_shndx >= in->ehdr->e_shnum) {
        fprintf(stderr, "lumina-ld: '%s' com shndx inválido\n", name);
        exit(1);
    }

    SecMap *m = &in->map[s->st_shndx];
    if (m->out_sec < 0) {
        fprintf(stderr, "lumina-ld: '%s' em seção não incluída (%s)\n",
                name, sec_name(in, s->st_shndx));
        exit(1);
    }
    return outsecs[m->out_sec].vaddr + m->out_off + s->st_value;
}

/* ================= Fase 4: relocação ================= */

static void apply_relocations(void) {
    for (int f = 0; f < ninputs; f++) {
        Input *in = &inputs[f];
        for (int i = 0; i < in->ehdr->e_shnum; i++) {
            Elf64_Shdr *sh = &in->shdrs[i];
            if (sh->sh_type != SHT_RELA) continue;

            int tgt = sh->sh_info;
            if (tgt < 0 || tgt >= in->ehdr->e_shnum) continue;
            SecMap *tm = &in->map[tgt];
            if (tm->out_sec < 0) continue;

            OutSec *o = &outsecs[tm->out_sec];
            Elf64_Rela *rl = (Elf64_Rela *)(in->data + sh->sh_offset);
            size_t n = sh->sh_size / sizeof(Elf64_Rela);

            for (size_t j = 0; j < n; j++) {
                uint64_t S   = sym_addr(in, ELF64_R_SYM(rl[j].r_info));
                int64_t  A   = rl[j].r_addend;
                uint64_t P   = o->vaddr + tm->out_off + rl[j].r_offset;
                uint8_t *loc = o->data  + tm->out_off + rl[j].r_offset;
                int      t   = ELF64_R_TYPE(rl[j].r_info);

                switch (t) {
                case R_X86_64_NONE: break;

                case R_X86_64_64: {
                    uint64_t v = S + (uint64_t)A;
                    memcpy(loc, &v, 8);
                    break;
                }
                case R_X86_64_PC32:
                case R_X86_64_PLT32: {
                    int64_t v = (int64_t)(S + (uint64_t)A - P);
                    if (v < INT32_MIN || v > INT32_MAX) {
                        fprintf(stderr,
                            "lumina-ld: PC32 fora de alcance (S=%lx P=%lx)\n",
                            (unsigned long)S, (unsigned long)P);
                        exit(1);
                    }
                    int32_t v32 = (int32_t)v;
                    memcpy(loc, &v32, 4);
                    break;
                }
                case R_X86_64_32: {
                    uint32_t v = (uint32_t)(S + (uint64_t)A);
                    memcpy(loc, &v, 4);
                    break;
                }
                case R_X86_64_32S: {
                    int32_t v = (int32_t)(S + (uint64_t)A);
                    memcpy(loc, &v, 4);
                    break;
                }
                case R_X86_64_PC64: {
                    int64_t v = (int64_t)(S + (uint64_t)A - P);
                    memcpy(loc, &v, 8);
                    break;
                }
                case R_X86_64_GOTPCREL:
                case R_X86_64_GOTPCRELX:
                case R_X86_64_REX_GOTPCRELX: {
                    uint8_t *op = loc - 3;
                    if ((op[0] & 0xF8) == 0x48 && op[1] == 0x8b &&
                        (op[2] & 0xC7) == 0x05) {
                        op[1] = 0x8d;
                        int32_t v = (int32_t)(S + (uint64_t)A - P);
                        memcpy(loc, &v, 4);
                    } else {
                        fprintf(stderr,
                            "lumina-ld: GOTPCRELX não relaxável em 0x%lx "
                            "(op=%02x %02x %02x)\n",
                            (unsigned long)P, op[0], op[1], op[2]);
                        exit(1);
                    }
                    break;
                }
                default:
                    fprintf(stderr, "lumina-ld: reloc tipo %d não suportada\n", t);
                    exit(1);
                }
            }
        }
    }
}

/* ================= Fase 5: escreve EXEC ELF ================= */

#ifdef LEGACY_RWX
static void write_output(const char *path, uint64_t entry) {
    uint8_t *buf = calloc(1, g_file_end);
    if (!buf) die("calloc");

    Elf64_Ehdr *eh = (Elf64_Ehdr *)buf;
    memcpy(eh->e_ident, ELFMAG, SELFMAG);
    eh->e_ident[EI_CLASS]   = ELFCLASS64;
    eh->e_ident[EI_DATA]    = ELFDATA2LSB;
    eh->e_ident[EI_VERSION] = EV_CURRENT;
    eh->e_ident[EI_OSABI]   = ELFOSABI_SYSV;
    eh->e_type      = ET_EXEC;
    eh->e_machine   = EM_X86_64;
    eh->e_version   = EV_CURRENT;
    eh->e_entry     = entry;
    eh->e_phoff     = sizeof(Elf64_Ehdr);
    eh->e_shoff     = 0;
    eh->e_flags     = 0;
    eh->e_ehsize    = sizeof(Elf64_Ehdr);
    eh->e_phentsize = sizeof(Elf64_Phdr);
    eh->e_phnum     = 1;
    eh->e_shentsize = 0;
    eh->e_shnum     = 0;
    eh->e_shstrndx  = SHN_UNDEF;

    uint64_t memsz = align_up(g_mem_end + HEAP_FOLGA, PAGE_SIZE);

    Elf64_Phdr *ph = (Elf64_Phdr *)(buf + sizeof(Elf64_Ehdr));
    ph->p_type   = PT_LOAD;
    ph->p_flags  = PF_R | PF_W | PF_X;
    ph->p_offset = 0;
    ph->p_vaddr  = BASE_ADDR;
    ph->p_paddr  = BASE_ADDR;
    ph->p_filesz = g_file_end;
    ph->p_memsz  = memsz;
    ph->p_align  = PAGE_SIZE;

    for (int i = 0; i < N_OUT_SECS; i++) {
        if (outsecs[i].nobits || !outsecs[i].size) continue;
        uint64_t off = outsecs[i].vaddr - BASE_ADDR;
        memcpy(buf + off, outsecs[i].data, outsecs[i].size);
    }

    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0755);
    if (fd < 0) die(path);
    if (write(fd, buf, g_file_end) != (ssize_t)g_file_end) die("write");
    close(fd);
    free(buf);

    fprintf(stderr,
            "[lumina-ld] %s ok (entry=0x%lx, %lu bytes, RWX legacy)\n",
            path, (unsigned long)entry, (unsigned long)g_file_end);
}
#else
static void write_output(const char *path, uint64_t entry) {
    uint8_t *buf = calloc(1, g_file_end);
    if (!buf) die("calloc");

    Elf64_Ehdr *eh = (Elf64_Ehdr *)buf;
    memcpy(eh->e_ident, ELFMAG, SELFMAG);
    eh->e_ident[EI_CLASS]   = ELFCLASS64;
    eh->e_ident[EI_DATA]    = ELFDATA2LSB;
    eh->e_ident[EI_VERSION] = EV_CURRENT;
    eh->e_ident[EI_OSABI]   = ELFOSABI_SYSV;
    eh->e_type      = ET_EXEC;
    eh->e_machine   = EM_X86_64;
    eh->e_version   = EV_CURRENT;
    eh->e_entry     = entry;
    eh->e_phoff     = sizeof(Elf64_Ehdr);
    eh->e_shoff     = 0;
    eh->e_flags     = 0;
    eh->e_ehsize    = sizeof(Elf64_Ehdr);
    eh->e_phentsize = sizeof(Elf64_Phdr);
    eh->e_phnum     = 2;
    eh->e_shentsize = 0;
    eh->e_shnum     = 0;
    eh->e_shstrndx  = SHN_UNDEF;

    uint64_t rx_filesz = g_rx_end;
    uint64_t rw_offset = g_rx_end;
    uint64_t rw_vaddr  = BASE_ADDR + rw_offset;
    uint64_t rw_filesz = g_file_end - rw_offset;
    uint64_t rw_memsz  = align_up(g_mem_end + HEAP_FOLGA, PAGE_SIZE) - rw_offset;

    if (rw_filesz == 0 && rw_memsz == 0) {
        rw_memsz = align_up(HEAP_FOLGA, PAGE_SIZE);
    }

    Elf64_Phdr *ph = (Elf64_Phdr *)(buf + sizeof(Elf64_Ehdr));

    ph[0].p_type   = PT_LOAD;
    ph[0].p_flags  = PF_R | PF_X;
    ph[0].p_offset = 0;
    ph[0].p_vaddr  = BASE_ADDR;
    ph[0].p_paddr  = BASE_ADDR;
    ph[0].p_filesz = rx_filesz;
    ph[0].p_memsz  = rx_filesz;
    ph[0].p_align  = PAGE_SIZE;

    ph[1].p_type   = PT_LOAD;
    ph[1].p_flags  = PF_R | PF_W;
    ph[1].p_offset = rw_offset;
    ph[1].p_vaddr  = rw_vaddr;
    ph[1].p_paddr  = rw_vaddr;
    ph[1].p_filesz = rw_filesz;
    ph[1].p_memsz  = rw_memsz;
    ph[1].p_align  = PAGE_SIZE;

    if (rw_vaddr < BASE_ADDR + rx_filesz) {
        fprintf(stderr,
            "lumina-ld: BUG — segmentos RX/RW sobrepostos "
            "(rx_end=0x%lx, rw_start=0x%lx)\n",
            (unsigned long)(BASE_ADDR + rx_filesz),
            (unsigned long)rw_vaddr);
        exit(1);
    }

    for (int i = 0; i < N_OUT_SECS; i++) {
        if (outsecs[i].nobits || !outsecs[i].size) continue;
        uint64_t off = outsecs[i].vaddr - BASE_ADDR;
        memcpy(buf + off, outsecs[i].data, outsecs[i].size);
    }

    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0755);
    if (fd < 0) die(path);
    if (write(fd, buf, g_file_end) != (ssize_t)g_file_end) die("write");
    close(fd);
    free(buf);

    fprintf(stderr,
            "[lumina-ld] %s ok (entry=0x%lx, file=%lu B, "
            "RX=[0x%lx..0x%lx) sz=%lu, RW=[0x%lx..0x%lx) filesz=%lu memsz=%lu)\n",
            path, (unsigned long)entry, (unsigned long)g_file_end,
            (unsigned long)BASE_ADDR,
            (unsigned long)(BASE_ADDR + rx_filesz),
            (unsigned long)rx_filesz,
            (unsigned long)rw_vaddr,
            (unsigned long)(rw_vaddr + rw_memsz),
            (unsigned long)rw_filesz,
            (unsigned long)rw_memsz);
}
#endif /* LEGACY_RWX */

/* ================= main ================= */

int main(int argc, char **argv) {
    const char *out = NULL;
    inputs = calloc(argc + 1, sizeof(Input));
    if (!inputs) die("calloc");

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-o")) {
            if (++i >= argc) err("-o exige argumento");
            out = argv[i];
        } else if (!strcmp(argv[i], "-e") || !strcmp(argv[i], "--entry")) {
            if (++i >= argc) err("-e exige argumento");
            entry_sym = argv[i];
        } else if (argv[i][0] == '-') {
            fprintf(stderr, "lumina-ld: flag desconhecida '%s'\n", argv[i]);
            exit(1);
        } else {
            inputs[ninputs++] = load_input(argv[i]);
        }
    }
    if (!out)     err("faltou -o <saida>");
    if (!ninputs) err("nenhum .o de entrada");

    merge_sections();
    build_gsyms();

    GSymbol *st = find_gsym(entry_sym);
    if (!st) {
        fprintf(stderr, "lumina-ld: símbolo de entrada '%s' não encontrado\n",
                entry_sym);
        exit(1);
    }
    uint64_t entry = sym_addr(&inputs[st->in_idx], st->sym_idx);

    apply_relocations();
    write_output(out, entry);
    return 0;
}