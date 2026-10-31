"""Deterministic incident report and optional assisted rewriting (FSD RF5/RF7).

The report of both Spanish versions is produced by `templates` from the closed
`brief`; `compose` adds assisted writing when a provider is configured and the
`guard` accepts the rewrite. Nothing in this package decides a finding, a level
or a count: those come from the detection engine and the risk classifier.
"""

from app.reporting.brief import build_brief
from app.reporting.compose import compose_report
from app.reporting.templates import SECTION_KEYS, VERSIONS, render_sections

__all__ = ["build_brief", "compose_report", "render_sections", "SECTION_KEYS", "VERSIONS"]
