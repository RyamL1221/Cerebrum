"""Replicated-logic memory conditions replicated_mem0 and
replicated_inhouse.

Every agent runs the kernel's own memory pipeline library
(``aios.memory.pipeline``) in its own process space, against the backend
directly; see docs/REPLICATED_LOGIC.md in AIOS.
"""
