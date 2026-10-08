.PHONY: all decompile analyse clean

# which contract to analyse:  make NAME=Other
NAME = Max

GIGAHORSE = $(CURDIR)/..
ADDON     = $(GIGAHORSE)/souffle-addon
OUT       = $(GIGAHORSE)/.temp/$(NAME)/out
UV       := $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)
SMACROS   = -M "GIGAHORSE_DIR=$(GIGAHORSE)/ BULK_ANALYSIS="

all: decompile analyse

decompile:
	solc --bin-runtime --overwrite -o . $(NAME).sol
	cp $(NAME).bin-runtime $(NAME).hex
	cd .. && $(UV) run ./gigahorse.py -C clients/visualizeout.py --restart mytests/$(NAME).hex
	python3 cfg.py $(OUT) > cfg.dot
	-command -v dot >/dev/null && dot -Tpng cfg.dot -o cfg.png

# Compile the client once (~75s) instead of letting souffle interpret it on every
# run (~5s each). Rebuilt automatically whenever rw_client.dl changes.
rw_client.bin: rw_client.dl
	souffle -o $@ -L $(ADDON) $(SMACROS) rw_client.dl

# macOS strips DYLD_* from signed binaries such as make, so the functor library
# path has to be set on the recipe line rather than inherited.
analyse: rw_client.bin
	mkdir -p out
	DYLD_LIBRARY_PATH=$(ADDON) ./rw_client.bin -F $(OUT) -D out
	@echo "=== R/W SET (function, op, slot, condition) ==="
	@printf '%-10s %-3s %-12s %s\n' function op slot condition
	@awk -F'\t' '{printf "%-10s %-3s %-12s %s\n", $$1, $$2, $$3, $$4}' out/RWSetOne.csv
	@echo "=== PRECONDITIONS (revert-guarded: bounds / overflow checks) ==="
	@awk -F'\t' '{printf "%-10s %-3s %-10s %s\n", $$1, $$2, $$3, $$4}' out/Precondition.csv
	@echo "=== storage reads (function, construct) ==="
	@cat out/StorageRead.csv
	@echo "=== storage writes (function, construct) ==="
	@cat out/StorageWrite.csv
	@echo "=== accesses that always happen (func, R/W, construct) ==="
	@cat out/UnguardedAccess.csv
	@echo "=== accesses that happen only under a condition ==="
	@cat out/GuardedAccess.csv
	@echo "=== branch conditions, expanded ==="
	@cat out/BranchCondition.csv
	@echo "=== what each condition depends on ==="
	@cat out/CondDependsOn.csv
	@echo "=== control dependence: merged value <- deciding condition ==="
	@cat out/PhiControlDep.csv
	@echo "=== n-way merges: value <- one of its conditions ==="
	@cat out/PhiCase.csv
	@echo "=== storage flow: stored var -> later loaded var ==="
	@cat out/StorageFlow.csv

clean:
	rm -rf ../.temp out $(NAME).hex $(NAME).bin-runtime cfg.dot cfg.png \
	       rw_client.bin rw_client.bin.cpp
