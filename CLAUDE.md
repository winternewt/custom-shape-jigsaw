# Coding Standards

- **Avoid nested try-catch**: try/catch often just hides errors; only use when errors are unavoidable.
- **Type hints**: Mandatory for all Python code.
- **Pathlib**: Always use for all file paths.
- **No relative imports**: Always use absolute imports.
- **No inline imports**: All imports must be at the module top level.
  - **Override**: `numpy` may be imported inline inside the functions that depend on it. This is an
    intentional architectural decision so the numpy backend can be made optional later; functions
    raise `NotImplementedError` when numpy is absent.
- **Polars**: Prefer over Pandas. Use lazyframes (`scan_parquet`) and streaming (`sink_parquet`).
- **Data Pattern**: Use `data/input`, `data/interim`, `data/output`.
- **Typer CLI**: Mandatory for all CLI tools.
- **Pydantic 2**: Use for API boundaries, config, and external input validation. Internal data
  flowing to Reflex state uses TypedDicts (zero overhead, native Reflex serialization).
- **Built-in logging**: Used for structured logging and action tracking.
- **Pay attention to terminal warnings**: Always check terminal output for warnings.
- **No placeholders**: Never use `/my/custom/path/` in code.
- **No legacy support**: Refactor aggressively; do not keep old API functions.
- **Dependency Management**: Use `uv sync` and `uv add`. NEVER use `uv pip install`.
- **Versions**: Do not hardcode versions in `__init__.py`; use `pyproject.toml`.
- **Avoid `__all__`**: Avoid `__init__.py` with `__all__` as it confuses where things are located.
- **Self-Correction**: If you make an API mistake that leads to a system error, you MUST update this
  file with the correct API usage or pattern.

## Project-specific notes

- Python floor is `>=3.11`, bounded by numpy 2.3+ (its real minimum), not arbitrary pinning.
- Package: import name `custom_shape_jigsaw`, distribution `custom-shape-jigsaw`, code under `src/`.
- This is a headless port of `CustomShapeJigsawJs/` (kept in-repo as the reference implementation).
