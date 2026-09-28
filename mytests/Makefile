.PHONY: all clean

# which contract to analyse
NAME = Max

all:
	solc --bin-runtime --overwrite -o . $(NAME).sol
	cp $(NAME).bin-runtime $(NAME).hex
	cd .. && uv run ./gigahorse.py -C clients/visualizeout.py --restart mytests/$(NAME).hex
	python3 cfg.py ../.temp/$(NAME)/out > cfg.dot
	dot -Tpng cfg.dot -o cfg.png
	open cfg.png
	cat ../.temp/$(NAME)/out/contract.tac
# -D out, not -D . : Gigahorse's libraries dump ~50 debug relations, and with
# "." they land in mytests. Keeping them in out/ leaves the directory clean.
	mkdir -p out
	souffle -F ../.temp/$(NAME)/out -D out -L ../souffle-addon rw_client.dl -M "GIGAHORSE_DIR=$$(cd .. && pwd)/ BULK_ANALYSIS="
	@echo "=== storage reads (function, construct) ==="
	@cat out/StorageRead.csv
	@echo "=== storage writes (function, construct) ==="
	@cat out/StorageWrite.csv
	@echo "=== branch conditions, expanded ==="
	@cat out/BranchCondition.csv
	@echo "=== what each condition depends on ==="
	@cat out/CondDependsOn.csv

clean:
	rm -rf ../.temp out $(NAME).hex $(NAME).bin-runtime cfg.dot cfg.png
