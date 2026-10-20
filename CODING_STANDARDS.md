# Coding Standards

Status: binding for every change; the Standards axis of code review checks
this file (see the `code-review` skill). Rules are checkable — if a rule
cannot be checked against a diff, it does not belong here.

## Toolchain (non-negotiable, mechanical)

- Python 3.12, managed with `uv` (`uv run ...`, `uv sync --all-groups`).
- `ruff format` (line length 88) + `ruff check` (E, W, F) — both must pass.
- `mypy src` must pass (`python_version` 3.12, `warn_return_any` off:
  numpy ufunc results are typed `Any` by the stubs).
- `uv run pytest` must pass. Tests import with `--import-mode=importlib`;
  `pythonpath = ["."]` in pyproject makes `experiments.*` importable.
- Commands: `make test`, `make lint`, `make format`.

## Architecture (the load-bearing rules)

1. **Two worlds, one direction.** `src/light_router/` is the router stack —
   what would run on a boat. `experiments/` is the virtual world — the
   harness, simulations, reporting, fixtures. Experiments import from the
   library; **the library never imports from experiments**. A new module
   goes where its users are: if only experiments call it, it lives in
   `experiments/`.
2. **CF Dataset is canonical** (Compatibility rule 1). Loaders produce
   CF-compliant xarray Datasets; routers and the harness consume them.
   `WeatherGrid` is the transitional internal numpy view — it must not
   appear in any public interface or docstring example.
3. **The Router seam** (rule 2). `route(start, finish, start_time) -> Route`
   is the entire contract. In-repo algorithms subclass `BaseRouter`
   (nominal, validated); the future oracle subprocess adapter satisfies the
   `Router` protocol structurally and must not inherit from our code.
   Weather, polar and config bind at construction (`RouterFactory`), never
   per call.
4. **No upward imports.** `models` imports nothing from the package;
   `routing` imports `models`; `weather_data` imports `models`. Nothing in
   `src/` imports `harness`/`simulation`/`reporting` — those live in
   `experiments/`. One sanctioned exception: `WeatherGrid.to_grib2` (the
   GRIB2 serialization symmetry, an explicit maintainer decision) imports
   its encoder lazily from `weather_data.grib`, which imports `models` at
   module level — the cycle exists only at call time and both ends are
   ours. New code does not add exceptions to this rule.
5. **The public API is a decision.** `light_router/__init__.py` `__all__` is
   the installed surface; adding an entry is deliberate, removing one is a
   breaking change to note in the PR.

## Code style

- **Docstrings**: every public module, class, and function. Dataclass fields
  are documented by a **docstring below each attribute** (see `WeatherGrid`,
  `Route`, `RouterConfig` for the pattern), including **units** — kt, nm,
  deg, "hours since scenario start". The class docstring stays a one-to-two
  line summary of the concept.
- **Units are never implicit.** If a value is knots, nautical miles, or
  hours-since-something, the name or docstring says so.
- **Naming**: modules `lowercase_snake`; dataclasses are domain nouns
  (`PolarTable`, `ForecastCycle`); private helpers take a leading underscore.
  Domain abbreviations (tws, twa, vmg, grib) are fine; ad-hoc ones are not.
- **Comments describe behavior and why — never narration** ("now we do X").
  A comment that restates the code is deleted, not maintained.
- **Type hints everywhere**, including private helpers. `from __future__
  import annotations` at the top of every module.
- **Vectorize or justify.** Per-point Python loops at hot paths (isochrone
  expansion, grid sampling) are a bug, not a style choice — the router
  samples thousands of points per level.

## Error handling

- Validate at boundaries: dataclass `__post_init__` for constructed data,
  `ValueError` with an actionable message at parse/load boundaries.
- No silent fallbacks. An offline fallback or default is explicit,
  documented in the docstring, and visible in the output (e.g.
  `CycleRecord.config = None` means "no data this cycle", it is recorded,
  not swallowed).

## Tests

- `src/light_router/` is tested — the library is the contract.
- `experiments/` has **no tests yet** (deliberate; revisit when experiments
  stabilize). Existing tests that cover moved experiment code stay with
  their modules as the regression net.
- Behavior-preserving refactors are validated **bit-identically**: rerun
  the ccv data-pack staircase and diff `passage.csv` / `cycles.csv` against
  the pre-refactor run.

## Workflow

- Changes land as unstaged working-tree edits for review first; nothing is
  committed or pushed without explicit approval.
- Specs: the Nextcloud collective (LowDataSailing) is the source of truth;
  `specs/*.md` are PR-review mirrors. Update the collective first.
- Run directories (`runs/`), data packs and caches (`data/`) are never
  committed.
