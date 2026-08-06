"""ASTERISM desktop UI — Dash + pywebview (SPEC §11).

Follows the GliaAnalysis / NED-Net idiom (SPEC §12): a server-side session store, a
fixed sidebar, a top tab bar, and per-page `layout(sid)` functions. The UI is a thin
shell over `asterism.core` — it never computes stats or draws figures itself, it just
calls the (tested, UI-free) core and displays the result.
"""
