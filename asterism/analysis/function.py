"""Plotting a function: 'Y = ...' in X with named constants (no Qt)."""

from __future__ import annotations

import ast

import numpy as np

from .models import _ALLOWED, _FUNCS, x_tree


def parse(text: str) -> tuple[object, list[str]]:
    """Compile 'Y = A*exp(-K*X)'; returns the code and the constants it uses (in order)."""
    expr = text.split("=", 1)[1] if "=" in text else text
    expr = expr.replace("^", "**").strip()
    if not expr:
        raise ValueError("Type an equation, such as Y = A*exp(-K*X).")
    tree = x_tree(expr)                       # lowercase x is X too
    names: list[str] = []
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"Not allowed in an equation: {type(node).__name__}")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in _FUNCS):
            raise ValueError("Unknown function in the equation.")
        if isinstance(node, ast.Name) and id(node) not in called and node.id not in _FUNCS \
                and node.id != "X" and node.id not in names:
            names.append(node.id)
    return compile(tree, "<function>", "eval"), names


def evaluate(text: str, params: dict[str, float], xs) -> np.ndarray:
    code, names = parse(text)
    missing = [n for n in names if n not in params]
    if missing:
        raise ValueError("No value for " + ", ".join(missing) + ".")
    x = np.asarray(xs, float)
    env = dict(_FUNCS)
    env["X"] = x
    env.update({n: float(params[n]) for n in names})
    with np.errstate(all="ignore"):
        y = eval(code, {"__builtins__": {}}, env)
    return np.asarray(y, float) + 0 * x
