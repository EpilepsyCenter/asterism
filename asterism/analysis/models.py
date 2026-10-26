"""Nonlinear regression model library: Prism's equation families (functions; our names
follow the standard pharmacology / kinetics names, which are not Prism's to own).

Each model: key, family, name, formula (as shown to the user), parameter names, f(x, *p),
initial(x, y) → starting values, defaults (constraints such as Hill slope sign), and
derived quantities computed from the fit (EC50 from logEC50, half-life from K, …).
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np


@dataclass
class Model:
    key: str
    family: str
    name: str
    formula: str
    params: list[str]
    f: Callable
    initial: Callable
    derived: Callable | None = None          # (values dict) → {name: value}
    x_is_log: bool = False                   # X is log(concentration)
    linear: bool = False                     # linear in parameters (fit is exact)
    description: str = ""
    bounds: dict = field(default_factory=dict)   # default bounds: {param: (lo, hi)}


# ---------------------------------------------------------------------------
# Initial values from the data (Prism's idea: look at the data's range and shape)
# ---------------------------------------------------------------------------

def _ends(x, y):
    o = np.argsort(x)
    xs, ys = x[o], y[o]
    k = max(1, len(xs) // 5)
    return xs, ys, float(np.mean(ys[:k])), float(np.mean(ys[-k:]))


def _x_at_half(x, y, lo, hi):
    xs, ys = x[np.argsort(x)], y[np.argsort(x)]
    half = (lo + hi) / 2
    i = int(np.argmin(np.abs(ys - half)))
    return float(xs[i])


def _sigmoid_init(x, y, rising=None):
    xs, ys, first, last = _ends(x, y)
    bottom, top = float(np.min(y)), float(np.max(y))
    up = last >= first if rising is None else rising
    return bottom, top, _x_at_half(x, y, bottom, top), (1.0 if up else -1.0)


def _rate_init(x, y):
    xs, ys, first, last = _ends(x, y)
    span = float(np.ptp(x)) or 1.0
    return first, last, 3.0 / span


def _hyper_init(x, y):
    """Vmax/Bmax-like plateau and the X at half of it."""
    top = float(np.max(y)) * 1.1 if np.max(y) > 0 else 1.0
    pos = x[x > 0]
    half = _x_at_half(x, y, 0.0, top) if len(pos) else 1.0
    return top, max(half, float(np.min(pos)) if len(pos) else 1.0)


def _safe_pow10(v):
    return np.power(10.0, np.clip(v, -300, 300))


LN2 = math.log(2)

# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

MODELS: list[Model] = []


def _add(*a, **k) -> Model:
    m = Model(*a, **k)
    MODELS.append(m)
    return m


# Dose-response — stimulation ---------------------------------------------------
F_STIM = "Dose-response: stimulation"
_add("agonist_3", F_STIM, "log(agonist) vs. response (three parameters)",
     "Y = Bottom + (Top − Bottom) / (1 + 10^(LogEC50 − X))",
     ["Bottom", "Top", "LogEC50"],
     lambda x, b, t, l: b + (t - b) / (1 + _safe_pow10(l - x)),
     lambda x, y: _sigmoid_init(x, y, True)[:3],
     lambda v: {"EC50": 10 ** v["LogEC50"], "Span": v["Top"] - v["Bottom"]}, x_is_log=True,
     description="Standard slope (Hill slope 1). X is the logarithm of concentration.")
_add("agonist_4", F_STIM, "log(agonist) vs. response, variable slope (four parameters)",
     "Y = Bottom + (Top − Bottom) / (1 + 10^((LogEC50 − X) · HillSlope))",
     ["Bottom", "Top", "LogEC50", "HillSlope"],
     lambda x, b, t, l, h: b + (t - b) / (1 + _safe_pow10((l - x) * h)),
     lambda x, y: (*_sigmoid_init(x, y, True)[:3], 1.0),
     lambda v: {"EC50": 10 ** v["LogEC50"], "Span": v["Top"] - v["Bottom"]}, x_is_log=True,
     description="The most common dose-response model. X is the logarithm of concentration.")
_add("agonist_norm", F_STIM, "log(agonist) vs. normalized response",
     "Y = 100 / (1 + 10^(LogEC50 − X))", ["LogEC50"],
     lambda x, l: 100 / (1 + _safe_pow10(l - x)),
     lambda x, y: (_x_at_half(x, y, 0, 100),),
     lambda v: {"EC50": 10 ** v["LogEC50"]}, x_is_log=True,
     description="Responses normalized to run from 0 to 100.")
_add("agonist_norm_var", F_STIM, "log(agonist) vs. normalized response, variable slope",
     "Y = 100 / (1 + 10^((LogEC50 − X) · HillSlope))", ["LogEC50", "HillSlope"],
     lambda x, l, h: 100 / (1 + _safe_pow10((l - x) * h)),
     lambda x, y: (_x_at_half(x, y, 0, 100), 1.0),
     lambda v: {"EC50": 10 ** v["LogEC50"]}, x_is_log=True)
_add("agonist_conc_3", F_STIM, "[Agonist] vs. response (three parameters)",
     "Y = Bottom + X · (Top − Bottom) / (EC50 + X)", ["Bottom", "Top", "EC50"],
     lambda x, b, t, e: b + x * (t - b) / (e + x),
     lambda x, y: (float(np.min(y)), float(np.max(y)), _x_at_half(x, y, np.min(y), np.max(y)) or 1.0),
     description="X is concentration (not its logarithm).", bounds={"EC50": (0, np.inf)})
_add("agonist_conc_4", F_STIM, "[Agonist] vs. response, variable slope (four parameters)",
     "Y = Bottom + X^HillSlope · (Top − Bottom) / (X^HillSlope + EC50^HillSlope)",
     ["Bottom", "Top", "EC50", "HillSlope"],
     lambda x, b, t, e, h: b + np.power(np.abs(x), h) * (t - b) / (np.power(np.abs(x), h) + np.power(abs(e), h)),
     lambda x, y: (float(np.min(y)), float(np.max(y)), _x_at_half(x, y, np.min(y), np.max(y)) or 1.0, 1.0),
     bounds={"EC50": (0, np.inf)})

# Dose-response — inhibition ----------------------------------------------------
F_INH = "Dose-response: inhibition"
_add("inhibitor_3", F_INH, "log(inhibitor) vs. response (three parameters)",
     "Y = Bottom + (Top − Bottom) / (1 + 10^(X − LogIC50))", ["Bottom", "Top", "LogIC50"],
     lambda x, b, t, l: b + (t - b) / (1 + _safe_pow10(x - l)),
     lambda x, y: _sigmoid_init(x, y, False)[:3],
     lambda v: {"IC50": 10 ** v["LogIC50"], "Span": v["Top"] - v["Bottom"]}, x_is_log=True)
_add("inhibitor_4", F_INH, "log(inhibitor) vs. response, variable slope (four parameters)",
     "Y = Bottom + (Top − Bottom) / (1 + 10^((LogIC50 − X) · HillSlope))",
     ["Bottom", "Top", "LogIC50", "HillSlope"],
     lambda x, b, t, l, h: b + (t - b) / (1 + _safe_pow10((l - x) * h)),
     lambda x, y: (*_sigmoid_init(x, y, False)[:3], -1.0),
     lambda v: {"IC50": 10 ** v["LogIC50"], "Span": v["Top"] - v["Bottom"]}, x_is_log=True)
_add("inhibitor_norm", F_INH, "log(inhibitor) vs. normalized response",
     "Y = 100 / (1 + 10^(X − LogIC50))", ["LogIC50"],
     lambda x, l: 100 / (1 + _safe_pow10(x - l)),
     lambda x, y: (_x_at_half(x, y, 0, 100),), lambda v: {"IC50": 10 ** v["LogIC50"]}, x_is_log=True)
_add("inhibitor_norm_var", F_INH, "log(inhibitor) vs. normalized response, variable slope",
     "Y = 100 / (1 + 10^((LogIC50 − X) · HillSlope))", ["LogIC50", "HillSlope"],
     lambda x, l, h: 100 / (1 + _safe_pow10((l - x) * h)),
     lambda x, y: (_x_at_half(x, y, 0, 100), -1.0), lambda v: {"IC50": 10 ** v["LogIC50"]}, x_is_log=True)
_add("inhibitor_conc_3", F_INH, "[Inhibitor] vs. response (three parameters)",
     "Y = Bottom + (Top − Bottom) / (1 + X / IC50)", ["Bottom", "Top", "IC50"],
     lambda x, b, t, i: b + (t - b) / (1 + x / i),
     lambda x, y: (float(np.min(y)), float(np.max(y)), _x_at_half(x, y, np.min(y), np.max(y)) or 1.0),
     bounds={"IC50": (0, np.inf)})
_add("inhibitor_conc_4", F_INH, "[Inhibitor] vs. response, variable slope (four parameters)",
     "Y = Bottom + (Top − Bottom) / (1 + (X / IC50)^HillSlope)", ["Bottom", "Top", "IC50", "HillSlope"],
     lambda x, b, t, i, h: b + (t - b) / (1 + np.power(np.abs(x / i), h)),
     lambda x, y: (float(np.min(y)), float(np.max(y)), _x_at_half(x, y, np.min(y), np.max(y)) or 1.0, 1.0),
     bounds={"IC50": (0, np.inf)})

# Enzyme kinetics ------------------------------------------------------------------
F_ENZ = "Enzyme kinetics"
_add("michaelis_menten", F_ENZ, "Michaelis-Menten", "Y = Vmax · X / (Km + X)", ["Vmax", "Km"],
     lambda x, v, k: v * x / (k + x), lambda x, y: _hyper_init(x, y), bounds={"Km": (0, np.inf)},
     description="Initial velocity as a function of substrate concentration.")
_add("allosteric", F_ENZ, "Allosteric sigmoidal", "Y = Vmax · X^h / (Khalf^h + X^h)", ["Vmax", "Khalf", "h"],
     lambda x, v, k, h: v * np.power(np.abs(x), h) / (np.power(abs(k), h) + np.power(np.abs(x), h)),
     lambda x, y: (*_hyper_init(x, y), 1.0), bounds={"Khalf": (0, np.inf)})
_add("substrate_inhibition", F_ENZ, "Substrate inhibition", "Y = Vmax · X / (Km + X · (1 + X / Ki))",
     ["Vmax", "Km", "Ki"], lambda x, v, k, i: v * x / (k + x * (1 + x / i)),
     lambda x, y: (*_hyper_init(x, y), float(np.max(x)) * 2 or 1.0))

# Binding ----------------------------------------------------------------------------
F_BIND = "Binding"
_add("one_site_specific", F_BIND, "One site: specific binding", "Y = Bmax · X / (Kd + X)", ["Bmax", "Kd"],
     lambda x, b, k: b * x / (k + x), lambda x, y: _hyper_init(x, y), bounds={"Kd": (0, np.inf)})
_add("one_site_hill", F_BIND, "Specific binding with Hill slope", "Y = Bmax · X^h / (Kd^h + X^h)",
     ["Bmax", "Kd", "h"],
     lambda x, b, k, h: b * np.power(np.abs(x), h) / (np.power(abs(k), h) + np.power(np.abs(x), h)),
     lambda x, y: (*_hyper_init(x, y), 1.0), bounds={"Kd": (0, np.inf)})
_add("one_site_total", F_BIND, "One site: total binding (specific + nonspecific)",
     "Y = Bmax · X / (Kd + X) + NS · X + Background", ["Bmax", "Kd", "NS", "Background"],
     lambda x, b, k, ns, bg: b * x / (k + x) + ns * x + bg,
     lambda x, y: (*_hyper_init(x, y), 0.0, float(np.min(y))), bounds={"Kd": (0, np.inf)})
_add("two_sites_specific", F_BIND, "Two sites: specific binding",
     "Y = Bmax1 · X / (Kd1 + X) + Bmax2 · X / (Kd2 + X)", ["Bmax1", "Kd1", "Bmax2", "Kd2"],
     lambda x, b1, k1, b2, k2: b1 * x / (k1 + x) + b2 * x / (k2 + x),
     lambda x, y: (lambda t, h: (t / 2, h / 5, t / 2, h * 5))(*_hyper_init(x, y)),
     bounds={"Kd1": (0, np.inf), "Kd2": (0, np.inf)})
_add("competitive_one_site", F_BIND, "Competitive binding: one site (fit log IC50)",
     "Y = Bottom + (Top − Bottom) / (1 + 10^(X − LogIC50))", ["Bottom", "Top", "LogIC50"],
     lambda x, b, t, l: b + (t - b) / (1 + _safe_pow10(x - l)),
     lambda x, y: _sigmoid_init(x, y, False)[:3], lambda v: {"IC50": 10 ** v["LogIC50"]}, x_is_log=True)

# Exponential ----------------------------------------------------------------------
F_EXP = "Exponential"
_add("one_phase_decay", F_EXP, "One-phase decay", "Y = (Y0 − Plateau) · e^(−K·X) + Plateau",
     ["Y0", "Plateau", "K"],
     lambda x, y0, p, k: (y0 - p) * np.exp(-k * x) + p,
     lambda x, y: _rate_init(x, y),
     lambda v: {"Half-life": LN2 / v["K"] if v["K"] else math.inf, "Tau": 1 / v["K"] if v["K"] else math.inf,
                "Span": v["Y0"] - v["Plateau"]})
_add("two_phase_decay", F_EXP, "Two-phase decay",
     "Y = Plateau + SpanFast · e^(−KFast·X) + SpanSlow · e^(−KSlow·X)",
     ["Plateau", "SpanFast", "KFast", "SpanSlow", "KSlow"],
     lambda x, p, sf, kf, ss, ks: p + sf * np.exp(-kf * x) + ss * np.exp(-ks * x),
     lambda x, y: (lambda f, l, k: (l, (f - l) / 2, k * 3, (f - l) / 2, k / 3))(*_rate_init(x, y)),
     lambda v: {"Half-life (fast)": LN2 / v["KFast"] if v["KFast"] else math.inf,
                "Half-life (slow)": LN2 / v["KSlow"] if v["KSlow"] else math.inf})
_add("one_phase_association", F_EXP, "One-phase association", "Y = Y0 + (Plateau − Y0) · (1 − e^(−K·X))",
     ["Y0", "Plateau", "K"],
     lambda x, y0, p, k: y0 + (p - y0) * (1 - np.exp(-k * x)),
     lambda x, y: _rate_init(x, y),
     lambda v: {"Half-time": LN2 / v["K"] if v["K"] else math.inf, "Tau": 1 / v["K"] if v["K"] else math.inf,
                "Span": v["Plateau"] - v["Y0"]})
_add("exponential_growth", F_EXP, "Exponential growth", "Y = Y0 · e^(K·X)", ["Y0", "K"],
     lambda x, y0, k: y0 * np.exp(k * x),
     lambda x, y: (lambda f, l, k: (f if f else 1.0, abs(k) / 3))(*_rate_init(x, y)),
     lambda v: {"Doubling time": LN2 / v["K"] if v["K"] else math.inf})

# Growth ------------------------------------------------------------------------------
F_GROW = "Growth curves"
_add("logistic_growth", F_GROW, "Logistic growth", "Y = YM · Y0 / ((YM − Y0) · e^(−K·X) + Y0)",
     ["YM", "Y0", "K"], lambda x, ym, y0, k: ym * y0 / ((ym - y0) * np.exp(-k * x) + y0),
     lambda x, y: (float(np.max(y)) * 1.05, max(float(np.min(y)), 1e-6), 4.0 / (float(np.ptp(x)) or 1.0)))
_add("gompertz", F_GROW, "Gompertz growth", "Y = YM · (Y0 / YM)^(e^(−K·X))", ["YM", "Y0", "K"],
     lambda x, ym, y0, k: ym * np.power(np.abs(y0 / ym), np.exp(-k * x)),
     lambda x, y: (float(np.max(y)) * 1.05, max(float(np.min(y)), 1e-6), 3.0 / (float(np.ptp(x)) or 1.0)))

# Gaussian and peaks --------------------------------------------------------------------
F_PEAK = "Gaussian and peaks"
_add("gaussian", F_PEAK, "Gaussian", "Y = Amplitude · e^(−0.5 · ((X − Mean) / SD)²)",
     ["Amplitude", "Mean", "SD"],
     lambda x, a, m, s: a * np.exp(-0.5 * ((x - m) / s) ** 2),
     lambda x, y: (float(np.max(y)), float(x[np.argmax(y)]), (float(np.ptp(x)) or 1.0) / 6))
_add("lorentzian", F_PEAK, "Lorentzian", "Y = Amplitude / (1 + ((X − Center) / Width)²)",
     ["Amplitude", "Center", "Width"],
     lambda x, a, c, w: a / (1 + ((x - c) / w) ** 2),
     lambda x, y: (float(np.max(y)), float(x[np.argmax(y)]), (float(np.ptp(x)) or 1.0) / 6))

# Lines and polynomials (linear in the parameters) --------------------------------------
F_LIN = "Lines and polynomials"
_add("line", F_LIN, "Straight line", "Y = YIntercept + Slope · X", ["YIntercept", "Slope"],
     lambda x, a, b: a + b * x, lambda x, y: (float(np.mean(y)), 0.0), linear=True)
for order, names in ((2, ["B0", "B1", "B2"]), (3, ["B0", "B1", "B2", "B3"]), (4, ["B0", "B1", "B2", "B3", "B4"])):
    _add(f"poly{order}", F_LIN, f"Polynomial, {['', '', 'second', 'third', 'fourth'][order]} order",
         "Y = " + " + ".join(f"B{i}·X^{i}" if i > 1 else ("B1·X" if i == 1 else "B0") for i in range(order + 1)),
         names, (lambda o: (lambda x, *b: sum(b[i] * x ** i for i in range(o + 1))))(order),
         (lambda o: (lambda x, y: tuple([float(np.mean(y))] + [0.0] * o)))(order), linear=True)

# Sine wave -------------------------------------------------------------------------------
F_WAVE = "Sine waves"
_add("sine", F_WAVE, "Standard sine wave", "Y = Baseline + Amplitude · sin(2π·X / Wavelength + PhaseShift)",
     ["Baseline", "Amplitude", "Wavelength", "PhaseShift"],
     lambda x, b, a, w, ph: b + a * np.sin(2 * np.pi * x / w + ph),
     lambda x, y: (float(np.mean(y)), float(np.ptp(y)) / 2, (float(np.ptp(x)) or 1.0) / 2, 0.0))

BY_KEY = {m.key: m for m in MODELS}
FAMILIES = list(dict.fromkeys(m.family for m in MODELS))


# ---------------------------------------------------------------------------
# User-defined equations: "Y = <expression in X and parameters>"
# ---------------------------------------------------------------------------

_FUNCS = {"exp": np.exp, "log": np.log10, "ln": np.log, "log10": np.log10, "sqrt": np.sqrt,
          "abs": np.abs, "sin": np.sin, "cos": np.cos, "tan": np.tan, "pi": math.pi, "e": math.e}
_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
            ast.USub, ast.UAdd, ast.Constant, ast.Name, ast.Load, ast.Call, ast.Mod)


class _LowerX(ast.NodeTransformer):
    """Lowercase x means X (a constant called x would only ever be a mistake)."""

    def visit_Name(self, node):
        if node.id == "x":
            node.id = "X"
        return node


def x_tree(expr: str):
    return ast.fix_missing_locations(_LowerX().visit(ast.parse(expr, mode="eval")))


def compile_expression(body: str, names: set[str]):
    """Compile a formula that may use only `names`, numbers, + − × ÷ ^ and the functions
    above; anything else (attributes, imports, unknown names) is refused."""
    tree = ast.parse(body.replace("^", "**").strip(), mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"Not allowed in an equation: {type(node).__name__}")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in _FUNCS):
            raise ValueError("Unknown function in the equation.")
        if isinstance(node, ast.Name) and node.id not in _FUNCS and node.id not in names:
            raise ValueError(f"Unknown name in the equation: {node.id}")
    return compile(tree, "<equation>", "eval")


def user_model(text: str, initial: dict[str, float] | None = None) -> Model:
    """Parse 'Y = Bottom + (Top-Bottom)/(1+exp(-K*X))'. ^ means power, log is log10, ln is
    natural log. Every name other than X and the functions is a parameter."""
    expr = text.split("=", 1)[1] if "=" in text else text
    expr = expr.replace("^", "**").strip()
    tree = x_tree(expr)
    names = []
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"Not allowed in an equation: {type(node).__name__}")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in _FUNCS):
            raise ValueError("Unknown function in the equation.")
        if isinstance(node, ast.Name) and node.id not in _FUNCS and node.id != "X" and node.id not in names:
            if not (any(isinstance(p, ast.Call) and p.func is node for p in ast.walk(tree))):
                names.append(node.id)
    if not names:
        raise ValueError("The equation has no parameters to fit.")
    code = compile(tree, "<equation>", "eval")

    def f(x, *p):
        env = dict(_FUNCS)
        env["X"] = x
        env.update(zip(names, p))
        return eval(code, {"__builtins__": {}}, env) + 0 * x
    init = initial or {}
    return Model("user", "User-defined", "User-defined equation", "Y = " + expr.replace("**", "^"),
                 names, f, lambda x, y: tuple(init.get(n, 1.0) for n in names))
