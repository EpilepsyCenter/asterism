"""ASTERISM import layer (SPEC §5–6).

Turns a source file (TRACER cohort export, NED-Net results, QuantStudio, manual
template) into the canonical long-format `Dataset` (SPEC §3). Every guess it makes
is surfaced and overridable before it affects an analysis (SPEC §2: "Nothing is
inferred silently").

Pure functions only — no UI imports. The Dash layer wraps these; the golden-dataset
tests exercise them directly.
"""
