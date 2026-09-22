# Running Gigahorse on macOS

Every command needed, from a fresh machine to the decompiled output of
`mytests/Max.sol`, its control-flow graph and its data-flow graph.
Tested on macOS (Apple Silicon).

## Pipeline

Five stages sit between the source and the result. The last three are
independent consumers of the same intermediate data, and `make` runs all of
them in order.

| # | stage | tool | input | output |
|---|---|---|---|---|
| 1 | compile | `solc` | `Max.sol` | `Max.hex` — runtime bytecode |
| 2 | fact generation | `gigahorse.py` (Python) | `Max.hex` | `.temp/Max/*.facts` |
| 3 | decompile | `logic/main.dl` via Souffle | `.temp/Max/*.facts` | `.temp/Max/out/*.csv` (~95 files) |
| 4 | inline | `clientlib/function_inliner.dl` via Souffle | `.temp/Max/out/*.csv` | overwrites 26 of them |
| 5a | pretty-print | `clients/visualizeout.py` | `out/*.csv` | `contract.tac` |
| 5b | draw graphs | `cfg.py`, `dfg.py` | `out/*.csv` | `cfg.png`, `dfg.png` |
| 5c | analyse | `rw_client.dl` via Souffle | `out/*.csv` | `StorageRead.csv`, `StorageWrite.csv` |

The whole input to the analysis is stage 2's output: a disassembly expressed as
three tables — offset to opcode, offset to next offset, offset to pushed
constant. No control-flow graph, no functions and no variables are supplied;
all three are derived in stage 3.

## 1. Install dependencies

```
brew install boost z3 solidity graphviz
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

`graphviz` provides `dot`, used by the graph scripts in steps 7 and 8. `python3`
comes with the macOS Command Line Tools; if it is missing, install them with
`xcode-select --install`. The graph scripts use only the standard library, so
they need no Python packages of their own.

Check everything:

```
souffle --version
solc --version
uv --version
dot -V
python3 --version
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

`make` compiles `Max.sol` to runtime bytecode, decompiles it, draws the two
graphs described in steps 7 and 8, opens them, and prints the lifted
three-address IR:

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

## 7. Control-flow graph (CFG)

Which code can run after which. Nodes are basic blocks, edges are possible
transfers of control. `make` builds this, or run it directly:

```
python3 cfg.py > cfg.dot
dot -Tpng cfg.dot -o cfg.png
open cfg.png
```

Each node shows a block's full statement list in the same notation as
`contract.tac`, so a node here is exactly one `Begin block` section there, and
its arrows are that section's `prev=` and `succ=` lists.

```
solid black    jump
dashed black   fallthrough
bold blue      call into a private function
dotted blue    return from a private function
```

Functions are drawn as labelled boxes. Alongside the contract's own functions
you will see `__function_selector__` (the dispatcher solc generates to route
calls by their 4-byte selector), `fallback()`, and any private helpers the
compiler emitted — for example its overflow-checked `+` and `-`, each ending in
a `Panic(0x11)` revert.

`cfg.py` takes the output directory as an optional argument, for a contract
other than `Max`:

```
python3 cfg.py ../.temp/Foo/out > cfg.dot
```

## 8. Data-flow graph (DFG)

How values move. Nodes are individual statements, edges run from the single
statement that defines a variable to each statement that uses it. The IR is in
SSA form — every variable has exactly one definition — so these edges are exact
rather than approximate.

```
python3 dfg.py ../.temp/Max/out max > dfg.dot
dot -Tpng dfg.dot -o dfg.png
open dfg.png
```

The second argument filters to functions whose name contains that text. Drop it
to draw every function, which is considerably larger.

Storage and memory operations are colour-filled, since they are what a
read/write set is built from:

```
blue      SLOAD    storage read
red       SSTORE   storage write
green     MLOAD    memory read
yellow    MSTORE   memory write
```

Node labels match `cfg.py` and `contract.tac` line for line, so the three views
can be read against each other: a CFG node is one block, and each line inside it
is one DFG node.

```
contract.tac                    cfg.py node 0x4b         dfg.py nodes
0x51: v51 = SLOAD v4f(0x2)  ->  same line in the box  ->  node "0x51"
0x52: v52 = GT v51, v4d(0x1)    same line in the box      node "0x52"
```

Expect the DFG to fall into several disconnected islands. That is correct, not a
defect: def-use edges follow *variables*, and three things move values by other
means — storage (`SSTORE` to a slot, then `SLOAD` of the same slot), calls
(an argument becomes a different variable inside the callee), and control flow
(a `JUMPI` decides which island executes). The first of those is what a
read/write set captures.

## 9. Storage read/write set

Which storage slots the contract reads and writes. This is the only piece that
is an *analysis* rather than a rendering: `rw_client.dl` is a Souffle Datalog
program, run over the same relations the graphs are drawn from.

`make` runs it, or run it directly — it takes about two seconds, since the
facts already exist:

```
souffle -F ../.temp/Max/out -D . rw_client.dl \
        -M "GIGAHORSE_DIR=$(cd .. && pwd)/ BULK_ANALYSIS="
cat StorageRead.csv StorageWrite.csv
```

`-F` is the fact directory that every `.input` reads from, `-D` is where
`.output` writes, and `-M` passes macros to the C preprocessor:
`GIGAHORSE_DIR` so the include can locate the functor declarations, and
`BULK_ANALYSIS=` to suppress the library's debug outputs. Omitting the latter
produces stray `Fail.csv` and `PublicFunctionId.csv` files.

The whole analysis is two rules:

```prolog
#include "../clientlib/decompiler_imports.dl"

.decl StorageRead(func: Function, slot: Value)
.output StorageRead

StorageRead(func, slot) :-
  SLOAD(stmt, index, _),
  Variable_Value(index, slot),
  Statement_Block(stmt, block),
  InFunction(block, func).
```

Read it as: *a function reads a slot if there is an `SLOAD` inside it whose
slot operand is a variable with that constant value.* `:-` means "if", commas
mean "and", and a variable repeated across clauses forces a join — `index`
links the `SLOAD` to its constant, `stmt` links it to its block, `block` links
that to its function. `_` is a wildcard for a column that does not matter, here
the value loaded. `StorageWrite` is the same with `SSTORE`.

The client never names a file. `decompiler_imports.dl` declares each relation
and binds it to a filename with `.input`; the `-F` flag supplies the directory.
`SLOAD` is not read from anywhere — it is derived in `tac_instructions.dl` from
`TAC_Op.csv`, `TAC_Def.csv` and `TAC_Use.csv`.

Output for `Max.sol`:

```
=== storage reads (function, slot) ===
0x2d	0x0
0x2d	0x2
0x2d	0x1
=== storage writes (function, slot) ===
0x2d	0x0
```

`0x2d` is the entry-block address of `max()`; the second column is a storage
slot. Slots are assigned in declaration order, so this reads `b`, `a` and `c`
and writes `b`. Four `SLOAD` instructions produce three rows because a Datalog
relation is a set and slot 0 is read twice.

Two limitations worth knowing. The rule matches only slots that are
compile-time constants, so a `mapping` or dynamic array — whose slot is a
runtime `keccak256` — is skipped silently; handling those needs
`clientlib/storage_modeling/`. And an access inside a private helper is
attributed to the helper, not to its caller.

## Analysing your own contract

Replace `Max.sol` with your own contract, keeping the file name and the contract
name aligned — `solc` writes its artifact using the **contract** name, not the
file name. Then:

```
make clean
make
```

The `make` rule passes `max` as the DFG's function filter. If your function has
a different name, update that line or the data-flow graph will come out empty.

## Troubleshooting

`solc: No such file or directory` — solc is missing; see step 1.

`dot: command not found` — graphviz is missing; see step 1.

`Cannot find libfunctors.so` — step 3 did not complete. Re-run it.

`Library not loaded: libsoufflenum.so` — the `install_name_tool` line in step 3
was skipped. Run it, then `rm -rf ../cache` and run `make` again.

`<cstddef> tried including <stddef.h>` or `The build tool has reset ENV` — step 4
was skipped, or was undone by a `brew upgrade`. Re-run step 4, then `rm -rf ../cache`.

`Killed signal terminated program cc1plus` — out of memory. The four Datalog
programs compile in parallel and need roughly 2-3 GB each.

An empty graph, or one missing most nodes — the output directory is wrong or
stale. The scripts read `../.temp/<contract>/out`, which exists only after a
successful `make`.

After changing Souffle or rebuilding `souffle-addon`, always `rm -rf ../cache`
first. The cache key is an MD5 of the Datalog source only, so it does not notice
that the toolchain underneath it changed.
