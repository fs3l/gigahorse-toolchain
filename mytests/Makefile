# Compile Max.sol, decompile it, draw the CFG and DFG:  make
# Delete everything generated:                          make clean

.PHONY: all clean

all:
	solc --bin-runtime --overwrite -o . Max.sol
	cp Max.bin-runtime Max.hex
	cd .. && uv run ./gigahorse.py -C clients/visualizeout.py --restart mytests/Max.hex
	python3 cfg.py > cfg.dot
	dot -Tpng cfg.dot -o cfg.png
	python3 dfg.py ../.temp/Max/out max > dfg.dot
	dot -Tpng dfg.dot -o dfg.png
	open cfg.png dfg.png
	cat ../.temp/Max/out/contract.tac

clean:
	rm -rf ../.temp Max.hex Max.bin-runtime cfg.dot cfg.png dfg.dot dfg.png
