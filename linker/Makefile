# linker/Makefile
CC        = clang
CFLAGS    = -O2 -Wall -Wextra
RT_CFLAGS = -ffreestanding -fno-pic -fno-pie -fno-stack-protector \
            -fno-builtin -nostdlib -O2

all: lumina-ld runtime/start.o runtime/rt.o

lumina-ld: link.c
	$(CC) $(CFLAGS) $< -o $@

runtime/start.o: runtime/start.S
	$(CC) -c $< -o $@

runtime/rt.o: runtime/rt.c
	$(CC) $(RT_CFLAGS) -c $< -o $@

clean:
	rm -f lumina-ld runtime/*.o
	rm -f /tmp/hw.ll /tmp/hw.o /tmp/hw

.PHONY: all clean
