CC = gcc
CFLAGS = -O3 -std=c17 -Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wdouble-promotion -Wformat=2 -Werror -fopenmp
CPPFLAGS ?=
LDFLAGS ?= -fopenmp
LDLIBS ?= -lcrypto -lm
SOURCE_SHA := $(shell sha256sum a348425.c | cut -d' ' -f1)
MAKE_SHA := $(shell sha256sum Makefile | cut -d' ' -f1)
BIND = -DA348425_SOURCE_SHA='"$(SOURCE_SHA)"' -DA348425_MAKE_SHA='"$(MAKE_SHA)"'
.PHONY: all check clean
all: a348425
a348425: a348425.c Makefile
	$(CC) $(CPPFLAGS) $(BIND) $(CFLAGS) -o $@ a348425.c $(LDFLAGS) $(LDLIBS)
check:
	python3 -I -B ../check/a348425_package.py
clean:
	rm -f a348425
