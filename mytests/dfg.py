#!/usr/bin/env python3
"""Emit a Graphviz .dot data-flow (def-use) graph from Gigahorse output.

    python3 dfg.py [out-dir] [function-filter] > dfg.dot
    dot -Tpng dfg.dot -o dfg.png

Default out-dir is ../.temp/Max/out. With no filter every function is drawn;
pass a substring to restrict it, for example:

    python3 dfg.py ../.temp/Max/out max > dfg.dot

Every statement is a node, including CONST and JUMP, so the graph lines up
one-to-one with the blocks drawn by cfg.py and with contract.tac. Labels use
the same notation as contract.tac (v51, v4f(0x2), ...). Edges run from the
single statement defining a variable to each statement using it; the IR is in
SSA form, so these edges are exact.

    blue    SLOAD      storage read
    red     SSTORE     storage write
    green   MLOAD      memory read
    yellow  MSTORE     memory write
"""
import csv
import os
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "../.temp/Max/out"
FILTER = sys.argv[2] if len(sys.argv) > 2 else None

FILL = {
    "SLOAD": "#cfe8ff",
    "SSTORE": "#ffd0d0",
    "MLOAD": "#d6f5d6",
    "MSTORE": "#fff3c4",
}


def load(name):
    path = os.path.join(OUT, name)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [r for r in csv.reader(f, delimiter="\t") if r]


op_of = {s: o for s, o in load("TAC_Op.csv")}
block_of = {s: b for s, b in load("TAC_Block.csv")}
func_of = {b: f for b, f in load("InFunction.csv")}
names = {f: n for f, n in load("HighLevelFunctionName.csv")}
value_of = {v: val for v, val in load("TAC_Variable_Value.csv")}

defines = [(s, v) for s, v, _ in load("TAC_Def.csv")]
uses = [(s, v, int(n)) for s, v, n in load("TAC_Use.csv")]

def_of_var = {v: s for s, v in defines}
defs_by_stmt = {}
for s, v in defines:
    defs_by_stmt.setdefault(s, []).append(v)
uses_by_stmt = {}
for s, v, n in uses:
    uses_by_stmt.setdefault(s, []).append((n, v))


def vname(var):
    """Render a variable the way contract.tac does: 0x51 -> v51."""
    return "v" + var.replace("0x", "")


def operand(var):
    """v4f(0x2) for a constant, v51 for anything else."""
    val = value_of.get(var)
    return f"{vname(var)}({val})" if val else vname(var)


def keep(stmt):
    if FILTER is None:
        return True
    f = func_of.get(block_of.get(stmt))
    return f is not None and (FILTER in f or FILTER in names.get(f, ""))


def label(stmt):
    op = op_of.get(stmt, "?")
    args = " ".join(operand(v) for _, v in sorted(uses_by_stmt.get(stmt, [])))
    out = ", ".join(operand(v) for v in defs_by_stmt.get(stmt, []))
    body = f"{op} {args}".strip()
    return f"{stmt}: {out} = {body}" if out else f"{stmt}: {body}"


# Every statement in scope becomes a node, connected or not.
all_stmts = [s for s in op_of if keep(s)]

edges = []
for use_stmt, var, _ in uses:
    def_stmt = def_of_var.get(var)
    if def_stmt is not None and keep(def_stmt) and keep(use_stmt):
        edges.append((def_stmt, use_stmt, var))

by_func = {}
for stmt in all_stmts:
    by_func.setdefault(func_of.get(block_of.get(stmt)), []).append(stmt)

print("digraph DFG {")
print("  rankdir=TB; ranksep=0.4; nodesep=0.3;")
print('  node [shape=box fontname="Courier" fontsize=10];')

for i, (func, stmts) in enumerate(sorted(by_func.items(), key=lambda kv: str(kv[0]))):
    print(f"  subgraph cluster_{i} {{")
    print(f'    label="{names.get(func, func)}"; color=gray; style=rounded;')
    for stmt in sorted(stmts):
        fill = FILL.get(op_of.get(stmt))
        extra = f' style=filled fillcolor="{fill}"' if fill else ""
        print(f'    "{stmt}" [label="{label(stmt)}"{extra}];')
    print("  }")

for def_stmt, use_stmt, var in edges:
    print(f'  "{def_stmt}" -> "{use_stmt}" [label="{vname(var)}" fontsize=8];')

print("}")
