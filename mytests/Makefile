# Compile Max.sol and decompile it with Gigahorse:  make
# Delete generated files:                           make clean

.PHONY: all clean

all:
	solc --bin-runtime --overwrite -o . Max.sol
	cp Max.bin-runtime Max.hex
	cd .. && uv run ./gigahorse.py -C clients/visualizeout.py --restart mytests/Max.hex
	cat ../.temp/Max/out/contract.tac

clean:
	rm -rf ../.temp Max.hex Max.bin-runtime
