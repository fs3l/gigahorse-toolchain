.PHONY: all clean

all:
	solc --bin-runtime --overwrite -o . Max.sol
	cp Max.bin-runtime Max.hex
	cd .. && uv run ./gigahorse.py -C clients/visualizeout.py --restart mytests/Max.hex
	python3 cfg.py > cfg.dot
	dot -Tpng cfg.dot -o cfg.png
	python3 dfg.py ../.temp/Max/out foo > dfg.dot
	dot -Tpng dfg.dot -o dfg.png
	open cfg.png dfg.png
	cat ../.temp/Max/out/contract.tac
	souffle -F ../.temp/Max/out -D . -L ../souffle-addon rw_client.dl -M "GIGAHORSE_DIR=$$(cd .. && pwd)/ BULK_ANALYSIS="
	@echo "=== storage reads (function, construct) ==="
	@cat StorageRead.csv
	@echo "=== storage writes (function, construct) ==="
	@cat StorageWrite.csv

clean:
	rm -rf ../.temp Max.hex Max.bin-runtime cfg.dot cfg.png dfg.dot dfg.png \
		StorageRead.csv StorageWrite.csv
