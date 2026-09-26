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
function foo()() public {
    Begin block 0x43
    prev=[], succ=[0x61B0x43]
    =================================
    0x44: v44(0x4b) = CONST
    0x47: v47(0x61) = CONST
    0x4a: JUMP v47(0x61)
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
dashed red     edge that can never be taken
grey box       block that can never execute
```

`cfg.py` works out the grey blocks itself, from the decompiler's own relations,
and reads nothing from `rw_client.dl`. That is deliberate: the graph is what the
analysis gets checked against, so it must not be drawn from the analysis's own
conclusions. Dead blocks are marked rather than removed, so the `JUMPI` that
killed them stays on the page next to them as the evidence.

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

Which storage locations the contract reads and writes. This is the only piece that
is an *analysis* rather than a rendering: `rw_client.dl` is a Souffle Datalog
program, run over the same relations the graphs are drawn from.

`make` runs it. To run it on its own, `.temp` must already exist, so run `make` at
least once first:

```
souffle -F ../.temp/Max/out -D . -L ../souffle-addon rw_client.dl \
        -M "GIGAHORSE_DIR=$(cd .. && pwd)/ BULK_ANALYSIS="
cat StorageRead.csv StorageWrite.csv
```

`-F` is the fact directory that every `.input` reads from, `-D` is where `.output`
writes, and `-L` points at the `souffle-addon` functor library, which the storage
model needs for its 256-bit arithmetic (`add_256` and friends). `-M` passes macros
to the C preprocessor: `GIGAHORSE_DIR` so the includes can locate the functor
declarations, and `BULK_ANALYSIS=` to suppress the library's debug outputs.
Omitting the latter produces stray `Fail.csv` and `PublicFunctionId.csv` files.

### The three includes

| include | why it is there |
|---|---|
| `decompiler_imports.dl` | binds each `.csv` to a relation, and derives the per-opcode relations (`SLOAD`, `SSTORE`) along with `Statement_Block` and `InFunction` |
| `memory_modeling` | never referenced directly, but `storage_modeling` depends on it. It must come **first**, or the build fails with 58 `Undefined relation PHITrans` errors |
| `storage_modeling` | the storage analysis proper: `StorageConstruct`, `StorageLoad`, `StorageStore`, `StorageStmtKindAndConstruct` |

`memory_modeling` is load-bearing rather than incidental. A dynamic array element
lives at `keccak256(slot) + idx`, and solc writes the slot into *memory* before
hashing it — `MSTORE 0x0, 0x0` then `SHA3 0x0, 0x20`. Connecting those two
statements is memory modeling. Without it the `SHA3` cannot be tied to the value
being hashed, and the array is never recognised as an array.

### Reachability

Before the read/write rules run, the client works out which blocks can actually
execute. Gigahorse's constant folding often resolves a branch condition to a
literal, but the decompiler still emits both successors, so an `if (23 < 15)`
body sits in the CFG as ordinary code. These rules remove it.

```prolog
.decl ConstCondJump(block: Block, alwaysTaken: number)
ConstCondJump(block, 1) :- JUMPI(s, _, cond), Statement_Block(s, block), Variable_Value(cond, v), v != "0x0".
ConstCondJump(block, 0) :- JUMPI(s, _, cond), Statement_Block(s, block), Variable_Value(cond, "0x0").

.decl InfeasibleEdge(from: Block, to: Block)
InfeasibleEdge(f, t) :- ConstCondJump(f, 1), FallthroughEdge(f, t).
InfeasibleEdge(f, t) :- ConstCondJump(f, 0), LocalBlockEdge(f, t), !FallthroughEdge(f, t).

.decl FeasibleEdge(from: Block, to: Block)
FeasibleEdge(f, t) :- LocalBlockEdge(f, t), !InfeasibleEdge(f, t).

.decl ReachableBlock(block: Block)
ReachableBlock(b) :- FunctionEntry(b).
ReachableBlock(t) :- ReachableBlock(f), FeasibleEdge(f, t).
```

`ConstCondJump` finds a `JUMPI` whose condition Gigahorse already folded to a
constant. `InfeasibleEdge` then kills the successor that cannot be taken, and
`ReachableBlock` walks from every function entry over the surviving edges.

Solc inverts every source condition with `ISZERO` so that the fallthrough is the
then-branch, which is why the two polarities look reversed:

| source | after `ISZERO` | `ConstCondJump` | edge that dies |
|---|---|---|---|
| `if (15 > 13)` — true | `0` | `(block, 0)` | the **jump** edge, i.e. the skip path |
| `if (23 < 15)` — false | `1` | `(block, 1)` | the **fallthrough**, i.e. the body |

`Max.sol` contains one of each, so both rules of each pair are exercised. In
`bar()`:

```
0xc4S0x57: vc4V57(0x0) = LT vc2V57(0x17), vc0V57(0xf)    23 < 15  -> 0
0xc5S0x57: vc5V57(0x1) = ISZERO vc4V57(0x0)                       -> 1
0xc9S0x57: JUMPI vc6V57(0x42f6), vc5V57(0x1)
```

giving `ConstCondJump(0xbfB0x57, 1)`, then `InfeasibleEdge(0xbfB0x57, 0xcaB0x57)`,
which kills the block holding the `SLOAD` of `c`, the block holding its `SSTORE`,
and the join after them.

### The rules

Each read/write rule carries one extra clause, `ReachableBlock(block)`, so a
storage statement in dead code contributes nothing.

```prolog
StorageRead(func, cons) :-
  StorageLoad(stmt, cons, _),
  Statement_Block(stmt, block),
  ReachableBlock(block),
  InFunction(block, func).

StorageRead(func, cons) :-
  StorageStmtKindAndConstruct(stmt, $ArrayLength(), $Storage(), cons),
  SLOAD(stmt, _, _),
  Statement_Block(stmt, block),
  ReachableBlock(block),
  InFunction(block, func).
```

Read the first as: *a function reads a construct if there is a storage load of it
inside some block, and that block belongs to the function.* `:-` means "if", commas
mean "and", and a variable repeated across clauses forces a join — `stmt` links the
load to its block, `block` links that to its function. `_` is a wildcard for a
column that does not matter, here the loaded variable.

Two rules sharing one head is Datalog's **or**: a row is derived if either rule
derives it. There is no ordering and no "else". The second rule exists because
`StorageLoad` only covers reads of a *value*; reading an array's length is
classified separately, under the kind `$ArrayLength()`. The `SLOAD(stmt, _, _)`
clause adds no new variable — it is a pure filter, and it is the only difference
between the read rule and its `SSTORE` counterpart, since a kind of `$ArrayLength()`
covers writes to the length too (`push`, `pop`).

`$Storage()` in the third position rejects `TLOAD`/`TSTORE`, the transient storage
opcodes from EIP-1153, which share the same relation.

`StorageWrite` is the same pair with `StorageStore` and `SSTORE`.

The client never names a file. `decompiler_imports.dl` declares each relation and
binds it to a filename with `.input`; the `-F` flag supplies the directory. `SLOAD`
is not read from anywhere — it is derived in `tac_instructions.dl` from `TAC_Op.csv`,
`TAC_Def.csv` and `TAC_Use.csv`.

### Storage constructs

The second output column is not a slot number but a `StorageConstruct`, an algebraic
data type that describes arbitrarily nested state. Read the nesting as a path:

| construct | meaning |
|---|---|
| `$Variable($Constant(0x2))` | the plain variable declared at slot 2 |
| `$Array($Constant(0x0))` | the array declared at slot 0, as a whole |
| `$Variable($Array($Constant(0x0)))` | an *element* of that array |
| `$Variable($Mapping($Constant(0x3)))` | a value of the mapping at slot 3 |

A slot number cannot express the third row. Slot 0 holds only the array's *length*;
the elements live at `keccak256(0) + idx`, and `idx` is a runtime value, so there is
no constant to print. That is why the output is a tree rather than a number, and it
is what an earlier slot-based version of this client got wrong — it reported nothing
for the write and a misleading `0x0` for the read.

The construct deliberately does not record *which* index. A function writing both
`array[i]` and `array[j]` produces one row, because all elements of an array are
summarised as a single location. The per-statement index variable is still available
from `StorageStmt_HighLevelUses` if that detail is needed.

Gigahorse documents this type in `clientlib/storage_modeling/README.md`, which also
links the paper describing the storage model.

### Output for `Max.sol`

`Max.sol` holds three functions: `pos()` guarded by `if (b > c)`, `foo()` by
`if (15 > 13)`, and `bar()` by `if (23 < 15)`. Slots follow declaration order, so
`b` is `0x0` and `c` is `0x1`.

```
=== storage reads (function, construct) ===
0x43	$Variable($Constant(0x0))
0x4d	$Variable($Constant(0x0))
0x4d	$Variable($Constant(0x1))
=== storage writes (function, construct) ===
0x43	$Variable($Constant(0x0))
0x4d	$Variable($Constant(0x0))
0x4d	$Variable($Constant(0x1))
```

`0x43` is `foo()` and `0x4d` is `pos()`. `bar()` is `0x57` and does not appear at
all: its guard is decided, so its body never runs and it touches no storage.
`cfg.py` greys the same four blocks, having reached that conclusion separately.

`pos()` stays in full. Its guard reads storage, so it cannot be decided — `foo()`
increments `b` on every call, and after enough calls `b > c` becomes true.

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

`Undefined relation PHITrans` (58 of them) — `memory_modeling` is included after
`storage_modeling` in `rw_client.dl`, or is missing. It must come first.

`cannot find user-defined operator add_256` — the `-L ../souffle-addon` flag is
missing from the souffle command.

`Cannot open fact file TAC_Def.csv` — `.temp` does not exist. Run `make` once before
running souffle on its own.

After changing Souffle or rebuilding `souffle-addon`, always `rm -rf ../cache`
first. The cache key is an MD5 of the Datalog source only, so it does not notice
that the toolchain underneath it changed.

## Note: measuring how long a run takes

A single `make` varies enough between runs that one measurement is not worth
much. To get an average over several runs — fish:

```
begin
  for i in (seq 5)
    /usr/bin/time -p make >/dev/null
  end
end 2>&1 | awk '/^real/{s+=$2; n++; printf "run %d: %.2f s\n", n, $2} END{printf "avg: %.3f s over %d runs\n", s/n, n}'
```

or bash / zsh:

```
for i in 1 2 3 4 5; do /usr/bin/time -p make >/dev/null; done 2>&1 \
  | awk '/^real/{s+=$2; n++; printf "run %d: %.2f s\n", n, $2} END{printf "avg: %.3f s over %d runs\n", s/n, n}'
```

`/usr/bin/time -p` writes `real`, `user` and `sys` to stderr for each run; the
surrounding block redirects the whole loop's stderr into `awk`, which prints each
run and averages at the end.

Run `make >/dev/null` once before measuring. The first run after a cold `../cache/`
compiles the Datalog programs to native binaries and takes minutes, and including
it would swamp the average. Every run afterwards is steady state.
