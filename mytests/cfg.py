#!/usr/bin/env python3
"""Emit a Graphviz .dot control-flow graph from Gigahorse output.

    python3 cfg.py [out-dir] > cfg.dot
    dot -Tpng cfg.dot -o cfg.png

Default out-dir is ../.temp/Max/out.

Each node is a basic block showing its full statement list, in the same
notation contract.tac uses, so a block here can be read against the matching
"Begin block" section there and against the nodes of dfg.py.

    solid black    jump
    dashed black   fallthrough
    bold blue      call into a private function
    dotted blue    return from a private function
"""
import csv
import os
import re
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "../.temp/Max/out"


def load(name):
    path = os.path.join(OUT, name)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [r for r in csv.reader(f, delimiter="\t") if r]


edges = [(a, b) for a, b in load("LocalBlockEdge.csv")]
fallthrough = {(a, b) for a, b in load("IRFallthroughEdge.csv")}
in_func = {b: f for b, f in load("InFunction.csv")}
names = {f: n for f, n in load("HighLevelFunctionName.csv")}
op_of = {s: o for s, o in load("TAC_Op.csv")}
block_of = {s: b for s, b in load("TAC_Block.csv")}
value_of = {v: val for v, val in load("TAC_Variable_Value.csv")}
calls = [(caller, func) for caller, func in load("IRFunctionCall.csv")]
call_returns = load("IRFunctionCallReturn.csv")

fun_returns = {}
for func, ret in load("IRFunction_Return.csv"):
    fun_returns.setdefault(func, []).append(ret)

defs_by_stmt = {}
for s, v, _ in load("TAC_Def.csv"):
    defs_by_stmt.setdefault(s, []).append(v)
uses_by_stmt = {}
for s, v, n in load("TAC_Use.csv"):
    uses_by_stmt.setdefault(s, []).append((int(n), v))

stmts_by_block = {}
for stmt, block in block_of.items():
    stmts_by_block.setdefault(block, []).append(stmt)

funcs = {}
for block, func in in_func.items():
    funcs.setdefault(func, []).append(block)


def address(stmt):
    """Sort key: the leading hex address, ignoring any inlining suffix."""
    m = re.match(r"0x[0-9a-fA-F]+", stmt)
    return int(m.group(0), 16) if m else 0


def operand(var):
    """v4f(0x2) for a constant, v51 for anything else."""
    name = "v" + var.replace("0x", "")
    val = value_of.get(var)
    return f"{name}({val})" if val else name


def statement(stmt):
    op = op_of.get(stmt, "?")
    args = " ".join(operand(v) for _, v in sorted(uses_by_stmt.get(stmt, [])))
    out = ", ".join(operand(v) for v in defs_by_stmt.get(stmt, []))
    body = f"{op} {args}".strip()
    return f"{stmt}: {out} = {body}" if out else f"{stmt}: {body}"


print("digraph CFG {")
print("  compound=true;")
print('  node [shape=box fontname="Courier" fontsize=9];')

for i, (func, blocks) in enumerate(sorted(funcs.items())):
    print(f"  subgraph cluster_{i} {{")
    print(f'    label="{names.get(func, func)}"; color=gray; style=rounded;')
    for block in sorted(blocks, key=address):
        lines = [statement(s) for s in sorted(stmts_by_block.get(block, []), key=address)]
        body = "\\l".join(lines)
        print(f'    "{block}" [label="{block}\\l{body}\\l"];')
    print("  }")

for a, b in edges:
    style = " [style=dashed]" if (a, b) in fallthrough else ""
    print(f'  "{a}" -> "{b}"{style};')

for caller, func in calls:
    if caller in in_func and func in in_func:
        print(f'  "{caller}" -> "{func}" [style=bold color=blue label="call"];')

for caller, func, cont in call_returns:
    for ret in fun_returns.get(func, []):
        if ret in in_func and cont in in_func:
            print(f'  "{ret}" -> "{cont}" [style=dotted color=blue label="return"];')

print("}")
