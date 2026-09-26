"""comment-derail-bench harness. See SPEC.md and bench/README.md."""

__version__ = "0.1.0"


def utf8_stdio() -> None:
    """Make stdout/stderr UTF-8 for the command-line entry points. Windows
    consoles default to cp1252, which cannot print report symbols such as
    '∈' or comment text copied from diffs."""
    import sys
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
