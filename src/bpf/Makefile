# Builds the pre-compiled BPF object shipped in lava-dispatcher-host.
# Build-time needs: clang, bpftool and the running kernel's BTF
# (/sys/kernel/btf/vmlinux, CONFIG_DEBUG_INFO_BTF=y, stock Debian 11+).

CLANG ?= clang
BPFTOOL ?= bpftool

all: lava_device_filter.bpf.o

# Delete targets whose recipe failed: a truncated vmlinux.h left behind looks
# up to date to make, and the next build compiles against an empty header.
.DELETE_ON_ERROR:

vmlinux.h:
	@test -r /sys/kernel/btf/vmlinux || { \
		echo "vmlinux.h: build host needs /sys/kernel/btf/vmlinux (CONFIG_DEBUG_INFO_BTF=y)" >&2; \
		exit 1; }
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@

%.bpf.o: %.bpf.c vmlinux.h
	# -Wno-missing-declarations: stock noise from anonymous declarations in
	# bpftool-generated vmlinux.h.
	$(CLANG) -target bpf -O2 -g -Wall -Wno-missing-declarations $(EXTRA_CFLAGS) -c $< -o $@

clean:
	rm -f vmlinux.h *.bpf.o

.PHONY: all clean
