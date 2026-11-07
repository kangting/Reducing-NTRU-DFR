CC ?= cc
PYTHON ?= python3
Q ?= 307
BUILD ?= build/q$(Q)
CFLAGS ?= -O3 -std=gnu11 -DNDEBUG -Wall -Wextra -fPIC
CPPFLAGS ?=
PROFILE_FLAG = -DCNTRU_Q=$(Q)
SOURCES = ct_radix.c cntru.c ct_ntt.c ct_ntt_avx2.c
HEADERS = ../common/ct_radix.c ../common/ct_radix.h ../common/ct_radix_generated.h ../common/ct_lookup.h radix.h cntru.h config.h profiles.h ct_util.h ct_ntt.h ntt_tables.h ntt16_tables.h sampling_tables.h
.PHONY: all test check-profiles sanitize clean ctgrind assembly
all: $(BUILD)/libcntru.so $(BUILD)/test_levels
$(BUILD):
	mkdir -p $@
check-profiles:
	$(PYTHON) gen_profiles.py --check
	$(PYTHON) gen_ntt.py --check
$(BUILD)/libcntru.so: $(SOURCES) $(HEADERS) | $(BUILD) check-profiles
	$(CC) $(PROFILE_FLAG) $(CPPFLAGS) $(CFLAGS) -shared $(SOURCES) -o $@
$(BUILD)/test_levels: test_levels.c $(SOURCES) $(HEADERS) | $(BUILD) check-profiles
	$(CC) $(PROFILE_FLAG) $(CPPFLAGS) $(CFLAGS) test_levels.c $(SOURCES) -o $@
test: $(BUILD)/test_levels
	./$(BUILD)/test_levels
sanitize:
	$(MAKE) Q=$(Q) BUILD=build/q$(Q)_sanitize CFLAGS='-O1 -g -std=c11 -Wall -Wextra -fsanitize=address,undefined -fno-omit-frame-pointer' test
$(BUILD)/ctgrind: ctgrind.c $(SOURCES) $(HEADERS) | $(BUILD) check-profiles
	$(CC) $(PROFILE_FLAG) $(CPPFLAGS) $(CFLAGS) -g ctgrind.c $(SOURCES) -o $@
ctgrind: $(BUILD)/ctgrind
	valgrind --tool=memcheck --error-exitcode=99 --track-origins=yes --log-file=$(BUILD)/ctgrind.log ./$(BUILD)/ctgrind
assembly: $(BUILD)/libcntru.so
	$(PYTHON) check_assembly.py --library $(BUILD)/libcntru.so --out $(BUILD)/assembly_check.json
clean:
	rm -rf build
