# Run Max.sol through Gigahorse:  make

all:
	solc --bin-runtime --overwrite -o . Max.sol
	cp Max.bin-runtime Max.hex
	cd ~/gigahorse-toolchain && uv run ./gigahorse.py -C clients/visualizeout.py --restart mytests/Max.hex
	cat ~/gigahorse-toolchain/.temp/Max/out/contract.tac
