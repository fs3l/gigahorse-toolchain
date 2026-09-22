# How the read/write set is computed

A walkthrough of a minimal example: the Solidity source, every stage between it
and the result, the analysis code, and the derivation of each output row.

The result being explained:

```
=== storage reads (function, slot) ===
0x2d	0x0
0x2d	0x2
0x2d	0x1
=== storage writes (function, slot) ===
0x2d	0x0
```

---

## 1. The contract

```solidity
// mytests/Max.sol
contract Max {
    uint256 b = 10;   // storage slot 0
    uint256 a = 1;    // storage slot 1
    uint256 c = 1;    // storage slot 2

    function max() public returns (uint256) {
        if (c > 1) {
            b = a + 1;
        } else {
            b = b - 1;
        }
        return b;
    }
}
```

Solc assigns storage slots in **declaration order**. The names `a`, `b`, `c` do
not survive compilation; only the slot numbers 0, 1, 2 exist in the bytecode.

The function is not `pure` or `view` because it both reads and writes state.
A `pure` version would have an empty read/write set by definition.

---

## 2. The pipeline

Five stages sit between the source and the result. Three of them are
independent consumers of the same intermediate data.

| # | stage | tool | input | output |
|---|---|---|---|---|
| 1 | compile | `solc` | `Max.sol` | `Max.hex` — runtime bytecode |
| 2 | fact generation | `gigahorse.py` (Python) | `Max.hex` | `.temp/Max/*.facts` |
| 3 | decompile | `logic/main.dl` via Souffle | `.temp/Max/*.facts` | `.temp/Max/out/*.csv` (~95 files) |
| 4 | inline | `clientlib/function_inliner.dl` via Souffle | `.temp/Max/out/*.csv` | overwrites 26 of them |
| 5a | pretty-print | `clients/visualizeout.py` | `out/*.csv` | `contract.tac` |
| 5b | draw graphs | `cfg.py`, `dfg.py` | `out/*.csv` | `cfg.png`, `dfg.png` |
| 5c | **analyse** | **`rw_client.dl` via Souffle** | **`out/*.csv`** | **`StorageRead.csv`, `StorageWrite.csv`** |

`make` runs all of them in order.

### Stage 1 — compile

```
solc --bin-runtime --overwrite -o . Max.sol
cp Max.bin-runtime Max.hex
```

`--bin-runtime`, not `--bin`. The latter is the *deployment* bytecode, which
runs once at construction, executes the initialisers `b = 10; a = 1; c = 1`,
and returns the runtime code. The runtime code is what lives at the contract
address and executes on every call, and it is what we analyse.

This is why `c > 1` cannot be constant-folded: the initialisation happened in
the constructor, so the runtime code must read slot 2 to find out what `c` is.

### Stage 2 — fact generation

`gigahorse.py` disassembles the hex and writes the input relations:

```
Statement_Opcode.facts     offset → opcode
Statement_Next.facts       offset → next offset
PushValue.facts            offset → pushed constant
bytecode.hex               the hex itself
PublicFunctionSignature.facts   (symlink) 4-byte selector → signature text
```

That is the **entire** input to the analysis: a disassembly expressed as tables.
No control-flow graph, no functions and no variables are supplied. All three are
derived in stage 3.

### Stage 3 — decompilation

`logic/main.dl` is a Datalog program. Souffle compiles it to C++, which is
compiled to a native binary and cached in `cache/` under an MD5 of the
preprocessed Datalog. The binary runs as:

```
cache/main.dl_compiled --facts=.temp/Max --output=.temp/Max/out
```

It reconstructs, from the flat instruction list:

- **the control-flow graph** — hard because every EVM jump is indirect: `JUMP`
  takes its destination from the stack, so the target must be computed by
  data-flow analysis rather than read off the instruction;
- **functions** — hard because the EVM has no instruction for internal calls.
  Solc implements one by pushing a return address, pushing arguments, and
  jumping; the callee returns by jumping to the address left on the stack.
  Gigahorse must recognise that pattern and infer function boundaries,
  argument counts and return counts;
- **variables** — the EVM is a stack machine with no variables at all. Gigahorse
  converts stack slots into SSA variables, one definition per instruction.

The output is about 95 CSV relations. Most are empty; an empty relation means
the property it describes does not hold for this contract.

### Stage 4 — inlining

`clientlib/function_inliner.dl` runs over stage 3's output and **overwrites 26
of the CSVs** with inlined versions, including all six that the analysis reads.
Consequences worth knowing:

- block identifiers such as `0x9cB0x35` appear, marking a block cloned into a
  particular call site (`B` = block copy, `S` = statement copy, `V` = variable);
- the analysis therefore describes the **post-inlining** IR;
- `InFunction.csv` has 37 rows while the decompiler's own `Analytics_Blocks`
  reports 33, because the analytics are computed before inlining. Same
  directory, two producers.

### Stage 5 — consumers

Three programs read the same directory and never talk to each other:

- `clients/visualizeout.py` joins five relations into the readable
  `contract.tac`;
- `cfg.py` and `dfg.py` join the same relations into Graphviz `.dot` files;
- `rw_client.dl` derives the read/write set.

This is the framework's design: every stage consumes relations and emits
relations, so a new analysis is just another program in the chain. There is no
plugin API.

---

## 3. The intermediate representation

`contract.tac` for `max()`, storage operations only:

| statement | source line | IR |
|---|---|---|
| `0x51` | `if (c > 1)` | `v51 = SLOAD v4f(0x2)` |
| `0x5b` | `b = a + 1` | `v5b = SLOAD v58(0x1)` |
| `0x69` | `b = a + 1` | `SSTORE v66(0x0), v64_0` |
| `0x73` | `b = b - 1` | `v73 = SLOAD v72(0x0)` |
| `0x81` | `b = b - 1` | `SSTORE v7e(0x0), v7c_0` |
| `0x85` | `return b` | `v85 = SLOAD v84(0x0)` |

How to read `0x51: v51 = SLOAD v4f(0x2)`:

- `0x51` before the colon is a **bytecode offset** — byte 81 of the runtime
  bytecode. Verifiable in `.temp/Max/contract.dasm`.
- `v51` is the SSA variable **defined** by that instruction. It is named after
  the defining offset because SSA guarantees one definition per instruction, so
  the address is a unique name.
- `SLOAD` pops one word (the slot number) and pushes one word (the value in
  that slot of this contract's persistent storage).
- `v4f` is the operand: the variable holding the slot number, defined at offset
  `0x4f` by a `PUSH1 0x02`.
- `(0x2)` is the **constant value** Gigahorse proved `v4f` holds. Note the two
  numbers mean different things: `0x4f` is *where the value was defined*, `0x2`
  is *what the value is*.

So this line reads storage slot 2, which is `c`.

---

## 4. The analysis code

`mytests/rw_client.dl`, in full:

```prolog
#include "../clientlib/decompiler_imports.dl"

.decl StorageRead(func: Function, slot: Value)
.output StorageRead

StorageRead(func, slot) :-
  SLOAD(stmt, index, _),
  Variable_Value(index, slot),
  Statement_Block(stmt, block),
  InFunction(block, func).

.decl StorageWrite(func: Function, slot: Value)
.output StorageWrite

StorageWrite(func, slot) :-
  SSTORE(stmt, index, _),
  Variable_Value(index, slot),
  Statement_Block(stmt, block),
  InFunction(block, func).

.decl UnresolvedStorageSlot(func: Function, stmt: Statement)
.output UnresolvedStorageSlot

UnresolvedStorageSlot(func, stmt) :-
  (SLOAD(stmt, index, _) ; SSTORE(stmt, index, _)),
  !Variable_Value(index, _),
  Statement_Block(stmt, block),
  InFunction(block, func).
```

### Where the data comes from

The client never names a file. The chain is three levels deep:

```
rule mentions      Statement_Block
                          │
decompiler_imports.dl     │  .input Statement_Block(IO="file",
binds name → filename ────┤         filename="TAC_Block.csv", delimiter="\t")
                          │
-F on the command line ───┘  -F ../.temp/Max/out
binds filename → directory
```

`#include` is handled by `cpp` before Souffle sees the file; it pastes in ~400
lines of `.decl` and `.input` pairs. That is why `SLOAD`, `Variable_Value`,
`Statement_Block` and `InFunction` exist without being defined here.

### `SLOAD` is derived, not loaded

There is no `SLOAD.csv`. `clientlib/tac_instructions.dl` contains one line,
`MAKEUNOP(SLOAD).`, which `cpp` expands into:

```prolog
.decl SLOAD(stmt: Statement, a: Variable, to: Variable)
SLOAD(stmt, a, to) :-
  Statement_Opcode(stmt, "SLOAD"),
  Statement_Defines(stmt, to, _),
  Statement_Uses(stmt, a, 0).
```

So `SLOAD` is itself a rule over three input relations, and its second argument
is the slot because `Statement_Uses(stmt, a, 0)` selects **operand 0**.

### Full dependency tree

```
StorageRead(func, slot)
├── SLOAD(stmt, index, _)              derived by a rule
│   ├── Statement_Opcode  ← TAC_Op.csv
│   ├── Statement_Defines ← TAC_Def.csv
│   └── Statement_Uses    ← TAC_Use.csv
├── Variable_Value        ← TAC_Variable_Value.csv
├── Statement_Block       ← TAC_Block.csv
└── InFunction            ← InFunction.csv
```

Six CSV files feed four clauses.

### How to read a rule

`:-` means **if**; the head is on the left, the body on the right; commas mean
**and**. Lowercase words are variables, and **a repeated variable forces a
join**:

```
SLOAD(stmt, index, _)          binds stmt and index
Variable_Value(index, slot)    the same index  ──┐  join
Statement_Block(stmt, block)   the same stmt   ──┘  join
InFunction(block, func)        the same block  ───  join
```

`_` is a wildcard for a column whose value is irrelevant — here, the value the
`SLOAD` returned, which a read set does not care about.

In the third rule, `;` means **or** and `!` means **negation**. Datalog requires
every variable inside a negation to be bound by a positive clause first; `index`
is bound by the `SLOAD`/`SSTORE`, so the negation is legal.

### Two properties that shape the output

**Relations are sets.** Deriving the same tuple twice stores it once.
Deduplication is the data model, not code that was written.

**There is no execution order.** Souffle evaluates all rules repeatedly until
nothing new can be derived — a fixpoint. Reordering the four clauses changes
the join plan and therefore the speed, never the result.

---

## 5. Derivation of each output row

Take statement `0x51`. Five rows across four files mention it:

```
TAC_Op.csv              0x51   SLOAD          it is an SLOAD
TAC_Def.csv             0x51   0x51    0      it defines v51
TAC_Use.csv             0x51   0x4f    0      its operand 0 is v4f
TAC_Variable_Value.csv  0x4f   0x2            v4f is the constant 2
TAC_Block.csv           0x51   0x4b           it lives in block 0x4b
InFunction.csv          0x4b   0x2d           that block belongs to function 0x2d
```

Binding the rule's variables against them:

```
stmt  = 0x51      from TAC_Op / TAC_Def / TAC_Use  (deriving SLOAD)
index = 0x4f
slot  = 0x2       from TAC_Variable_Value
block = 0x4b      from TAC_Block
func  = 0x2d      from InFunction
```

Every clause matches, so the rule fires: **`StorageRead(0x2d, 0x2)`**.

The same for all six storage instructions:

| statement | slot | block | function | derives |
|---|---|---|---|---|
| `0x51` | `0x2` | `0x4b` | `0x2d` | `StorageRead(0x2d, 0x2)` |
| `0x5b` | `0x1` | `0x58` | `0x2d` | `StorageRead(0x2d, 0x1)` |
| `0x73` | `0x0` | `0x6f` | `0x2d` | `StorageRead(0x2d, 0x0)` |
| `0x85` | `0x0` | `0x83` | `0x2d` | `StorageRead(0x2d, 0x0)` — duplicate |
| `0x69` | `0x0` | `0x65` | `0x2d` | `StorageWrite(0x2d, 0x0)` |
| `0x81` | `0x0` | `0x7d` | `0x2d` | `StorageWrite(0x2d, 0x0)` — duplicate |

**Six instructions, four rows.** `0x73` and `0x85` both derive
`StorageRead(0x2d, 0x0)`; the two `SSTORE`s both derive
`StorageWrite(0x2d, 0x0)`. Each is stored once, because a relation is a set.

`0x2d` is the entry-block address of `max()`. `PublicFunctionId.csv` shows
`0x2d  0x6ac5db19  max()` — the selector resolved against the signature
database.

Final result, with the names restored by hand:

| | slots | variables |
|---|---|---|
| reads | 0, 1, 2 | `b`, `a`, `c` |
| writes | 0 | `b` |

`c` is read by the condition, `a` by the then-branch, `b` by the else-branch and
again by `return b`; `b` is written on both branches.

---

## 6. The same derivation seen in the two graphs

The rule is a walk over both graphs:

| clauses | graph | role |
|---|---|---|
| `SLOAD`, `Variable_Value` | **data-flow graph** | follow a def-use edge from the `SLOAD` back to the constant feeding its operand |
| `Statement_Block`, `InFunction` | **control-flow graph** | follow containment: statement ∈ block ∈ function |

In `dfg.png`, statement `0x51` is a blue box labelled `0x51: v51 = SLOAD
v4f(0x2)`, with an incoming edge labelled `v4f` from the node `0x4f: v4f(0x2) =
CONST`. That edge is the `TAC_Use` row; the `(0x2)` in the label is the
`Variable_Value` row.

In `cfg.png`, the same line appears inside the box `0x4b`, which sits in the
cluster labelled `max()`.

Note what the rule does **not** use: none of the CFG's arrows. `LocalBlockEdge`
never appears. A read/write set does not depend on execution order or on which
branch runs — only on the access existing somewhere in the function. Both
branches' `SSTORE`s contribute even though exactly one executes at runtime. This
is a **may**-analysis: the union over all paths, which is the sound choice for
conflict detection, where missing a possible write would be unsafe.

---

## 7. Limitations

**Constant slots only.** `Variable_Value(index, slot)` matches only when the
slot is a compile-time constant. For a `mapping` or a dynamic array the slot is
`keccak256(key . base)`, computed at runtime, so the clause fails and that
access is skipped silently — the set would look complete while being wrong.

`UnresolvedStorageSlot` exists to make that visible: it lists every storage
instruction whose slot did not resolve. It is **empty** for this contract, which
is what certifies the four rows above as complete. Handling the non-constant
case requires `clientlib/storage_modeling/`, which reconstructs mappings, arrays
and structs from the SHA3 patterns.

**No transitivity through calls.** Every storage access here is directly inside
`max()`. If a private helper touched storage, the caller's set would not include
it. Fixing that means a recursive rule over `CallGraphEdge`.

**Storage only.** Memory (`MLOAD`/`MSTORE`) is excluded deliberately: it is
per-call scratch space, discarded when the call ends, so two transactions cannot
conflict through it. Transient storage (`TLOAD`/`TSTORE`) would belong in a
complete set; this contract has none.

---

## 8. Reproducing the result

```
cd mytests
make
```

`make` runs all five stages and prints the read/write set last. To re-run only
the analysis against facts that already exist, which takes about two seconds:

```
souffle -F ../.temp/Max/out -D . rw_client.dl \
        -M "GIGAHORSE_DIR=$(cd .. && pwd)/ BULK_ANALYSIS="
cat StorageRead.csv StorageWrite.csv
```

`-F` is the fact directory that every `.input` reads from, `-D` is where
`.output` writes, and `-M` passes macros to `cpp`: `GIGAHORSE_DIR` so the
include can locate the functor declarations, and `BULK_ANALYSIS=` to suppress
the library's debug outputs.

See `README.md` for installation and for the CFG and DFG.
