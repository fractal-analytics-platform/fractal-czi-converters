# CLAUDE.md

Fractal tasks to convert Zeiss CZI files into OME-Zarr. Conversion engine lives in
`ome-zarr-converters-tools` (shared across the sibling converters).

## Commands

All commands need a `pixi run -e dev` / `-e test` prefix (never bare python/pytest/ruff):

- `pixi run -e test pytest tests/` — test suite
- `pixi run -e dev chores` — full gate (ruff format/fix → pytest → pre-commit)
- `pixi run -e dev fractal-manifest check --package fractal_czi_converters` — validate the Fractal manifest

## Testing

Snapshot-based via the shared `ome_zarr_converters_tools.testing` helper; reference
JSON in `tests/data/Zeiss-CZI/snapshots/`. Regenerate with `--update-snapshots`. The
`--update-snapshots`/`--extended` options, the `extended` marker, and the
`update_snapshots` fixture come from `ome_zarr_converters_tools.testing.plugin`,
loaded via `pytest_plugins` in `tests/conftest.py` (deliberately not a pytest11 entry
point upstream, so coverage can measure it). `--extended` tests need the git-ignored
`tests/data-extended/`.

## Code Style

- Ruff: line length 88, target **py312** (Python `>=3.12` floor is deliberate —
  `common/acquisitions.py` uses PEP 695 generics; do not lower to match siblings)
- Google-style docstrings; type-checking via `ty`; spell-check via `typos` (false
  positives go in `_typos.toml`)
- Pydantic v2 models; `@validate_call` on task functions

## Changelog

Always update `CHANGELOG.md` (Features / Fix / API Breaking Changes / Chores / Documentation).
