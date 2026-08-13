# Contributing

Use Python 3.11+ and uv:

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
uv run epic-intel benchmark --suite smoke
```

For candidate experiments, change only `candidate/**`. For core changes, explain the
contract or threat-model impact and add focused tests. New benchmark data must be synthetic
or have documented redistribution rights, must contain no real row-level health data, and
must declare its license in the task file.

Pull requests that weaken a hard gate, expose expected answers to the candidate, silently
default a missing verifier to pass, treat assessment failure as normal risk, or enable a
side effect by default require an explicit security design review and will normally be
rejected.

