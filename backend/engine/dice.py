from __future__ import annotations

import random
import re


def do_roll(formula: str) -> dict:
    """Roll dice for formulas like 1d100, 3d6+2, 2d8-1, 1d6*5, 1d20+3."""
    m = re.match(
        r"^\s*(\d+)d(\d+)\s*(?:([+\-\*xX])\s*(\d+))?\s*$", formula.lower()
    )
    if not m:
        return {
            "error": True,
            "formula": formula,
            "rolls": [],
            "total": 0,
            "result_text": "Invalid formula",
        }

    count, sides = int(m.group(1)), int(m.group(2))
    op, mod = m.group(3), int(m.group(4)) if m.group(4) else None
    rolls = [random.randint(1, sides) for _ in range(count)]
    subtotal = sum(rolls)

    if op and mod is not None:
        if op == "+":
            total = subtotal + mod
        elif op == "-":
            total = subtotal - mod
        elif op in ("*", "x"):
            total = subtotal * mod
        else:
            total = subtotal
    else:
        total = subtotal

    return {
        "formula": formula,
        "rolls": rolls,
        "total": total,
        "result_text": f"Roll {formula}: {total}",
    }
