CC ?= cc
PYTHON ?= python3
VARIANT ?= ref
SRC := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ROOT := $(abspath $(SRC)/../../..)
CANONICAL_VARIANT := $(if $(filter portable,$(VARIANT)),ref,$(VARIANT))
TARGET := q211-$(CANONICAL_VARIANT)
BUILD := $(ROOT)/benchmarks/build/$(TARGET)
ISA := $(if $(filter ref,$(CANONICAL_VARIANT)),x86-64,x86-64-v3)
DEFINITIONS := $(if $(filter avx2,$(CANONICAL_VARIANT)),-DCNTRU_AVX2_NTT,)
FLAGS := -std=gnu11 -O3 -DNDEBUG -Wall -Wextra -fPIC -march=$(ISA) -mtune=generic $(DEFINITIONS) -I$(SRC)
SOURCES := $(addprefix $(SRC)/,cntru.c ct_ntt.c ct_ntt_avx2.c ct_radix.c)
OBJECTS := $(addprefix $(BUILD)/,cntru.o ct_ntt.o ct_ntt_avx2.o ct_radix.o)

.PHONY: all test check check-tables sanitize assembly ctgrind clean
all:
	$(PYTHON) $(ROOT)/benchmarks/build.py --targets $(TARGET) --cc $(CC)
test:
	$(PYTHON) $(ROOT)/benchmarks/build.py --targets $(TARGET) --cc $(CC) --test
check:
	$(PYTHON) $(ROOT)/benchmarks/build.py --targets $(TARGET) --cc $(CC) --check
check-tables:
	$(PYTHON) $(SRC)/verify_tables.py
	$(PYTHON) $(SRC)/gen_ntt16.py --check
sanitize:
	mkdir -p $(BUILD)
	$(CC) $(filter-out -O3 -DNDEBUG,$(FLAGS)) -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer $(SRC)/test_hardened.c $(SOURCES) -o $(BUILD)/sanitizer
	$(BUILD)/sanitizer
assembly: all
	$(PYTHON) $(SRC)/check_assembly.py --library $(BUILD)/libcntru.so --out $(BUILD)/assembly_check.json
ctgrind: all
	$(CC) $(FLAGS) -g $(SRC)/ctgrind.c $(OBJECTS) -o $(BUILD)/ctgrind
	valgrind --tool=memcheck --error-exitcode=99 --track-origins=yes --log-file=$(BUILD)/ctgrind.log $(BUILD)/ctgrind
clean:
	rm -rf $(BUILD)
