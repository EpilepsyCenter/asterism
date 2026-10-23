"""Mixed-effects model for repeated measures with missing values (Prism's method).

Prism fits repeated-measures data that have gaps with a mixed model: the main factors are
fixed, subjects are random, the covariance is compound symmetry (a subject variance that
may be negative, as in RM ANOVA), fitted by REML. With no missing values it gives the
same P values and multiple comparisons as RM ANOVA (Prism's guide; golden-tested here by
fitting complete Prism data both ways).

    y = Xβ + Σ_k Z_k u_k + e,   u_k ~ N(0, v_k I),  e ~ N(0, σ² I)

V = σ² H(λ), H = I + Σ λ_k Z_k Z_k', λ_k = v_k/σ²; σ² is profiled out of the REML
likelihood, so only λ (one value per random term) is searched. λ_k may be negative as
long as V stays positive definite.

Fixed effects: Type III Wald F tests, L β with effect coding. Denominator degrees of
freedom by the containment method (as SAS PROC MIXED does by default): an effect
contained in a random term (a between-subject factor in "subject") gets that term's rank
contribution; others get the residual df. With complete data these equal RM ANOVA's df.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import optimize
from scipy import stats as sps


@dataclass
class MixedFit:
    beta: np.ndarray
    cov: np.ndarray                 # covariance of beta
    sigma2: float                   # residual variance
    variances: list[float]          # one per random term
    loglik: float                   # REML log-likelihood
    loglik0: float                  # REML log-likelihood without the random terms
    n: int
    p: int
    df_resid: int
    df_terms: list[int]             # containment df of each random term
    extra: dict = field(default_factory=dict)

    def wald(self, L: np.ndarray) -> tuple[float, int]:
        L = np.atleast_2d(L)
        Lb = L @ self.beta
        q = np.linalg.matrix_rank(L)
        F = float(Lb @ np.linalg.solve(L @ self.cov @ L.T, Lb) / q)
        return F, int(q)

    def contrast(self, l: np.ndarray) -> tuple[float, float]:
        """Estimate and standard error of l·β."""
        return float(l @ self.beta), float(math.sqrt(max(l @ self.cov @ l, 0.0)))

    def lrt(self) -> tuple[float, int, float]:
        """Likelihood-ratio test of the random terms (was the matching effective?)."""
        chi = max(0.0, 2 * (self.loglik - self.loglik0))
        k = len(self.variances)
        return chi, k, float(sps.chi2.sf(chi, k))


def _profiled(y, X, H):
    """−2 REML log-likelihood with σ² profiled out, and the pieces needed afterwards."""
    n, p = X.shape
    try:
        Lc = np.linalg.cholesky(H)
    except np.linalg.LinAlgError:
        return math.inf, None
    Xs = np.linalg.solve(Lc, X)
    ys = np.linalg.solve(Lc, y)
    XtX = Xs.T @ Xs
    try:
        Lx = np.linalg.cholesky(XtX)
    except np.linalg.LinAlgError:
        return math.inf, None
    beta = np.linalg.solve(XtX, Xs.T @ ys)
    r = ys - Xs @ beta
    rss = float(r @ r)
    if rss <= 0:
        return math.inf, None
    s2 = rss / (n - p)
    logdet_h = 2 * float(np.log(np.diag(Lc)).sum())
    logdet_x = 2 * float(np.log(np.diag(Lx)).sum())
    dev = (n - p) * (math.log(2 * math.pi) + math.log(s2) + 1.0) + logdet_h + logdet_x
    return dev, (beta, s2, XtX)


def fit(y: np.ndarray, X: np.ndarray, Zs: list[np.ndarray]) -> MixedFit:
    y = np.asarray(y, float)
    n, p = X.shape
    if np.linalg.matrix_rank(X) < p:
        raise ValueError("The fixed effects can't be estimated: some combinations of factors have no values.")
    ZZ = [Z @ Z.T for Z in Zs]
    eye = np.eye(n)

    def H_of(lam):
        H = eye.copy()
        for l_, zz in zip(lam, ZZ):
            H += l_ * zz
        return H

    def obj(lam):
        return _profiled(y, X, H_of(lam))[0]

    k = len(Zs)
    if k == 1:
        # PD while 1 + λ·(largest cluster) > 0 for a single random intercept
        lo = -1.0 / max(np.linalg.eigvalsh(ZZ[0]).max(), 1.0) + 1e-9
        res = optimize.minimize_scalar(lambda v: obj([v]), bounds=(lo, 1e6), method="bounded",
                                       options={"xatol": 1e-12, "maxiter": 2000})
        lam = np.array([res.x])
        # bounded Brent can stall on a wide bracket; refine around the optimum
        for _ in range(2):
            w = max(abs(lam[0]) * 0.5, 1e-3)
            res = optimize.minimize_scalar(lambda v: obj([v]), bounds=(max(lo, lam[0] - w), lam[0] + w),
                                           method="bounded", options={"xatol": 1e-13, "maxiter": 2000})
            lam = np.array([res.x])
    else:
        best = None
        for start in (np.full(k, 0.5), np.full(k, 0.05), np.full(k, 2.0)):
            r_ = optimize.minimize(obj, start, method="Nelder-Mead",
                                   options={"xatol": 1e-10, "fatol": 1e-12, "maxiter": 20000})
            if best is None or r_.fun < best.fun:
                best = r_
        r2 = optimize.minimize(obj, best.x, method="BFGS", options={"gtol": 1e-10})
        lam = r2.x if np.isfinite(r2.fun) and r2.fun <= best.fun else best.x
    lam = _newton_polish(obj, np.asarray(lam, float))
    dev, (beta, s2, XtX) = _profiled(y, X, H_of(lam))
    dev0, (_, _, _) = _profiled(y, X, eye)
    cov = s2 * np.linalg.inv(XtX)
    rank_all = np.linalg.matrix_rank(np.hstack([X, *Zs]))
    df_terms = []
    for j in range(k):
        others = [Z for i, Z in enumerate(Zs) if i != j]
        df_terms.append(int(rank_all - np.linalg.matrix_rank(np.hstack([X, *others]))))
    return MixedFit(beta=beta, cov=cov, sigma2=float(s2), variances=[float(s2 * l_) for l_ in lam],
                    loglik=-dev / 2, loglik0=-dev0 / 2, n=n, p=p, df_resid=int(n - rank_all),
                    df_terms=df_terms)


def _newton_polish(obj, lam: np.ndarray, steps: int = 6) -> np.ndarray:
    """A few Newton steps on the REML deviance (finite differences) after the search, so the
    estimates are accurate to near machine precision rather than the search tolerance."""
    k = len(lam)
    for _ in range(steps):
        h = 1e-4 * np.maximum(np.abs(lam), 1e-2)
        f0 = obj(lam)
        g = np.zeros(k)
        Hm = np.zeros((k, k))
        for i in range(k):
            e = np.zeros(k)
            e[i] = h[i]
            fp, fm = obj(lam + e), obj(lam - e)
            g[i] = (fp - fm) / (2 * h[i])
            Hm[i, i] = (fp - 2 * f0 + fm) / h[i] ** 2
            for j in range(i):
                e2 = np.zeros(k)
                e2[j] = h[j]
                Hm[i, j] = Hm[j, i] = (obj(lam + e + e2) - obj(lam + e - e2) - obj(lam - e + e2)
                                       + obj(lam - e - e2)) / (4 * h[i] * h[j])
        if not np.all(np.isfinite(Hm)) or np.any(np.linalg.eigvalsh(Hm) <= 0):
            break
        step = np.linalg.solve(Hm, g)
        new = lam - step
        if not np.isfinite(obj(new)) or obj(new) > f0 + 1e-12:
            break
        lam = new
        if np.max(np.abs(step)) < 1e-12 * max(1.0, np.max(np.abs(lam))):
            break
    return lam


# ---------------------------------------------------------------------------
# Design matrices
# ---------------------------------------------------------------------------

def effect_codes(levels: np.ndarray, k: int) -> np.ndarray:
    X = np.zeros((len(levels), k - 1))
    for j in range(k - 1):
        X[levels == j, j] = 1.0
    X[levels == k - 1, :] = -1.0
    return X


def indicator(ids: np.ndarray) -> np.ndarray:
    u, inv = np.unique(ids, return_inverse=True)
    Z = np.zeros((len(ids), len(u)))
    Z[np.arange(len(ids)), inv] = 1.0
    return Z


def two_factor_design(a: np.ndarray, b: np.ndarray, A: int, B: int):
    """Effect-coded [1, A, B, A×B] and the column slices of each effect, plus a function
    giving the coefficient vector of a cell mean."""
    XA, XB = effect_codes(a, A), effect_codes(b, B)
    XAB = np.column_stack([XA[:, i] * XB[:, j] for i in range(A - 1) for j in range(B - 1)]) \
        if A > 1 and B > 1 else np.zeros((len(a), 0))
    X = np.column_stack([np.ones(len(a)), XA, XB, XAB])
    sl = {"a": slice(1, A), "b": slice(A, A + B - 1), "ab": slice(A + B - 1, X.shape[1])}

    def code(level, k):
        v = np.zeros(k - 1)
        if level < k - 1:
            v[level] = 1.0
        else:
            v[:] = -1.0
        return v

    def cell(i, j):
        ca, cb = code(i, A), code(j, B)
        return np.concatenate([[1.0], ca, cb, np.outer(ca, cb).ravel()])
    return X, sl, cell


def L_for(sl: slice, p: int) -> np.ndarray:
    idx = range(sl.start, sl.stop)
    L = np.zeros((len(idx), p))
    for r, c in enumerate(idx):
        L[r, c] = 1.0
    return L
