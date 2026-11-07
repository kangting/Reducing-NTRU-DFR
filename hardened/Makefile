CC ?= cc
PYTHON ?= python3
CFLAGS ?= -O3 -std=c11 -Wall -Wextra -Wpedantic
CPPFLAGS ?=
LDLIBS ?=
BUILD ?= build
SOURCES = ct_radix.c cntru.c ct_ntt.c ct_ntt_avx2.c
HEADERS = ../common/ct_radix.c ../common/ct_radix.h ../common/ct_radix_generated.h ../common/ct_lookup.h radix.h cntru.h ct_util.h ct_ntt.h ntt_tables.h ntt16_tables.h sampling_tables.h

.PHONY: all test sanitize clean assembly ctgrind check-tables
all: $(BUILD)/libcntru.so $(BUILD)/test_hardened
$(BUILD):
	mkdir -p $@
check-tables:
	$(PYTHON) verify_tables.py
$(BUILD)/libcntru.so: $(SOURCES) $(HEADERS) | $(BUILD) check-tables
	$(CC) $(CPPFLAGS) $(CFLAGS) -fPIC -shared $(SOURCES) -o $@ $(LDLIBS)
$(BUILD)/test_hardened: test_hardened.c $(SOURCES) $(HEADERS) | $(BUILD) check-tables
	$(CC) $(CPPFLAGS) $(CFLAGS) test_hardened.c $(SOURCES) -o $@ $(LDLIBS)
test: $(BUILD)/test_hardened
	./$(BUILD)/test_hardened
sanitize:
	$(MAKE) BUILD=build_sanitize CFLAGS='-O1 -g -std=c11 -Wall -Wextra -fsanitize=address,undefined -fno-omit-frame-pointer' test
assembly: $(BUILD)/libcntru.so
	$(PYTHON) check_assembly.py --library $(BUILD)/libcntru.so --out $(BUILD)/assembly_check.json
$(BUILD)/ctgrind: ctgrind.c $(SOURCES) $(HEADERS) | $(BUILD) check-tables
	$(CC) $(CPPFLAGS) $(CFLAGS) -g ctgrind.c $(SOURCES) -o $@ $(LDLIBS)
ctgrind: $(BUILD)/ctgrind
	valgrind --tool=memcheck --error-exitcode=99 --track-origins=yes --log-file=$(BUILD)/ctgrind.log ./$(BUILD)/ctgrind
clean:
	rm -rf build build_sanitize build_native
