  cd ~/gigahorse-toolchain/souffle-addon

  sed -i '' 's/ -fopenmp//g' Makefile

  env CPATH=/opt/homebrew/include LIBRARY_PATH=/opt/homebrew/lib make

  ln -sf libsoufflenum.so libfunctors.dylib

  set L (pwd)/libsoufflenum.so
  
  install_name_tool -id $L $L

  otool -D libsoufflenum.so

  cd ~/gigahorse-toolchain

  sed -i '' '/append("-D")/d' src/runners.py

  sed -i '' 's/append(macro_def)/append(f"-D{macro_def}")/' src/runners.py

  sed -i '' 's/resource\.setrlimit.*/return/' src/runners.py

  grep -n -A1 "set_memory_limit\|cpp_macros.append" src/runners.py

  uv sync

  mkdir -p mytests

  nano mytests/Max.sol

// SPDX-License-Identifier: MIT
  pragma solidity ^0.8.0;

  contract Max {
      function max(uint256 b) public pure returns (uint256) {
          if (b > 1) {
              b = b + 1;
          } else {
              b = b - 1;
          }
          return b;
      }
  }

  solc --bin-runtime --overwrite -o build mytests/Max.sol

  cp build/Max.bin-runtime mytests/Max.hex

  wc -c mytests/Max.hex

  set c clients/visualizeout.py

  uv run ./gigahorse.py -C $c --restart mytests/Max.hex  

  cat .temp/Max/out/contract.tac


