"""ASTERISM import layer (SPEC §5–6).

Turns a lab export (TRACER cohort export, NED-Net results) into the canonical long-format
`Dataset` (SPEC §3); `asterism.io.labs` lays that out as typed tables, and
`asterism.io.quantstudio` reads qPCR runs. Every guess it makes
is surfaced and overridable before it affects an analysis (SPEC §2: "Nothing is
inferred silently").

Pure functions only — no UI imports.
"""
