# Running Gigahorse on macOS

Every command needed, from a fresh machine to the decompiled output of
`mytests/Max.sol`. Tested on macOS (Apple Silicon).

## 1. Install dependencies

```
brew install boost z3 solidity
brew install souffle-lang/souffle/souffle
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Do **not** add `--HEAD` to the Souffle install. The development branch fails with
`variable not grounded: diff`. This installs Souffle 2.4.

Add `uv` to your PATH:

```
fish_add_path ~/.local/bin            # fish
export PATH="$HOME/.local/bin:$PATH"  # bash / zsh
```

Check all four:

```
souffle --version
solc --version
uv --version
```

## 2. Clone the repository

```
cd ~
git clone --recursive git@github.com:fs3l/gigahorse-toolchain.git
cd gigahorse-toolchain
```

The `--recursive` flag is required — it fetches the `souffle-addon` submodule.
If you forgot it: `git submodule update --init --recursive`.

This uses SSH, which needs a key registered with GitHub. Create one with
`ssh-keygen -t ed25519`, add `~/.ssh/id_ed25519.pub` under GitHub → Settings →
SSH and GPG keys, and verify with `ssh -T git@github.com`.

## 3. Build the Souffle functor library

```
cd souffle-addon
sed -i '' 's/ -fopenmp//g' Makefile
env CPATH=/opt/homebrew/include LIBRARY_PATH=/opt/homebrew/lib make
ln -sf libsoufflenum.so libfunctors.dylib
install_name_tool -id "$PWD/libsoufflenum.so" libsoufflenum.so
cd ..
```

`make` ends with `mappings_tests ... Error 201`. Ignore it — that is a test, and
the library is already built. Confirm with:

```
ls souffle-addon/libsoufflenum.so souffle-addon/libfunctors.dylib
```

## 4. Patch Souffle's compile configuration

This file belongs to Homebrew, not to this repository, so it must be patched
locally:

```
F=$(ls /opt/homebrew/Cellar/souffle/*/bin/souffle-compile.py)
chmod u+w $F
sed -i '' '/"compiler"/s|: ".*"|: "/usr/bin/g++"|' $F
sed -i '' '/"includes"/s|: ".*"|: ""|' $F
sed -n '3p;7p' $F
```

The last command should print:

```
  "compiler": "/usr/bin/g++",
  "includes": "",
```

Repeat this step after any `brew upgrade souffle`.

## 5. Set up the Python environment

```
uv sync
```

## 6. Run

```
cd mytests
make
```

`make` compiles `Max.sol` to runtime bytecode, decompiles it, and prints the
lifted three-address IR:

```
function max(uint256)() public {
    Begin block 0x2d
    prev=[], succ=[0xcaB0x2d]
    =================================
    0x2e: v2e(0x47) = CONST
    ...
```

The listing is also saved to `../.temp/Max/out/contract.tac`.

The first run compiles four Datalog programs to native binaries and takes about
two minutes. They are cached in `../cache/`, so later runs take a few seconds.

To start over:

```
make clean
make
```

## Analysing your own contract

Replace `Max.sol` with your own contract, keeping the file name and the contract
name aligned — `solc` writes its artifact using the **contract** name, not the
file name. Then:

```
make clean
make
```

## Troubleshooting

`solc: No such file or directory` — solc is missing; see step 1.

`Cannot find libfunctors.so` — step 3 did not complete. Re-run it.

`Library not loaded: libsoufflenum.so` — the `install_name_tool` line in step 3
was skipped. Run it, then `rm -rf ../cache` and run `make` again.

`<cstddef> tried including <stddef.h>` or `The build tool has reset ENV` — step 4
was skipped, or was undone by a `brew upgrade`. Re-run step 4, then `rm -rf ../cache`.

`Killed signal terminated program cc1plus` — out of memory. The four Datalog
programs compile in parallel and need roughly 2-3 GB each.

After changing Souffle or rebuilding `souffle-addon`, always `rm -rf ../cache`
first. The cache key is an MD5 of the Datalog source only, so it does not notice
that the toolchain underneath it changed.

## Files

| file | purpose |
|---|---|
| `Max.sol` | Solidity source — the only input |
| `Makefile` | `make`, `make clean` |
| `SETUP-macos.txt` | macOS setup notes |
