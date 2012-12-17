LDFLAGS += -static
BINARY = mkfifo
ARCH = $(shell uname -m)
DIST = $(ARCH)/$(BINARY)

all: $(DIST)

test: all
	cd $(shell dirname $(DIST)) && sh ../tests/mkfifo.sh

$(DIST): $(BINARY)
	mkdir -p $(shell dirname $(DIST))
	ln $< $@

clean:
	$(RM) -f $(BINARY) $(DIST)
	[ -d $(ARCH) ]i && rmdir $(ARCH) || true
