# Decompile the committed Max.hex:              make
# Regenerate Max.hex from Max.sol (needs solc): make hex
# Delete generated files:                       make clean

.PHONY: all hex clean

all:
	cd .. && uv run ./gigahorse.py -C clients/visualizeout.py --restart mytests/Max.hex
	cat ../.temp/Max/out/contract.tac

hex:
	solc --bin-runtime --overwrite -o . Max.sol
	cp Max.bin-runtime Max.hex

clean:
	rm -rf ../.temp Max.bin-runtime
