# Repository structure: standards survey and reorganization proposal for Light-Router

Research note (2026-09-30). Every claim below is cited to a primary source that was
fetched during this research; quotes are verbatim or close paraphrases. Sources that
could not be fetched are flagged in [Section 1](#1-sources-consulted).

## 1. Sources consulted

| # | Source | URL |
|---|--------|-----|
| 1 | PyPA Packaging User Guide — tutorial | https://packaging.python.org/en/latest/tutorials/packaging-projects/ |
| 2 | PyPA — "src layout vs flat layout" discussion | https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/ |
| 3 | Scientific Python Development Guide (root) | https://learn.scientific-python.org/development/ |
| 4 | Same guide — "Packaging" tutorial | https://learn.scientific-python.org/development/tutorials/packaging/ |
| 5 | Same guide — "Simple packaging" guide | https://learn.scientific-python.org/development/guides/packaging-simple/ |
| 6 | scientific-python/cookie (formerly cookiecutter) README + sp-repo-review checks | https://github.com/scientific-python/cookie |
| 7 | cjolowicz/cookiecutter-hypermodern-python | https://github.com/cjolowicz/cookiecutter-hypermodern-python |
| 8 | pytest — "Good Integration Practices" | https://docs.pytest.org/en/stable/explanation/goodpractices.html |
| 9 | pyOpenSci Python Package Guide — "Package Structure & Layout" | https://www.pyopensci.org/python-package-guide/package-structure-code/python-package-structure.html |
| 10 | Cookiecutter Data Science (CCDS) v2 docs | https://cookiecutter-data-science.drivendata.org/ |
| 11 | CCDS "Opinions" | https://cookiecutter-data-science.drivendata.org/opinions/ |
| 12 | DrivenData — "Cookiecutter Data Science V2" announcement | https://drivendata.co/blog/ccds-v2 |
| 13 | M. Nygard — "Documenting Architecture Decisions" (2011) | https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions.html |
| 14 | MADR (adr.github.io) | https://adr.github.io/madr/ |
| 15 | uv — "Project structure and files" | https://docs.astral.sh/uv/concepts/projects/layout/ |
| 16 | Hatch — Introduction (`hatch new`) | https://hatch.pypa.io/latest/intro/ |
| 17 | numpy repo tree + `benchmarks/README.rst` | https://github.com/numpy/numpy |
| 18 | scikit-learn repo tree | https://github.com/scikit-learn/scikit-learn |
| 19 | xarray repo tree | https://github.com/pydata/xarray |
| 20 | DVC — "Project Structure" | https://dvc.org/doc/user-guide/project-structure |
| 21 | DVC — "Data versioning" get-started | https://dvc.org/doc/start/data-management/data-versioning |
| 22 | Diátaxis framework | https://diataxis.fr/ |

Fetch problems: the GitHub page for `scientific-python/cookiecutter` did not render
(JavaScript-only); the README of its successor repo `scientific-python/cookie` was
fetched from `raw.githubusercontent.com` instead. `dvc.org/doc/user-guide/dvc-yaml-files`
404s (the Project Structure page is a stub linking to it); DVC conventions were taken
from the Project Structure and Data Versioning pages instead.

## 2. What the standards say

### 2.1 Package layout: src vs flat

- PyPA's tutorial builds the canonical src-layout skeleton: `LICENSE`, `pyproject.toml`,
  `README.md`, `src/<package>/`, `tests/`, and says "The directory containing the Python
  files should match the project name" [1].
- PyPA's dedicated discussion lists the behavioral differences: "The src layout
  requires installation of the project to be able to run its code, and the flat layout
  does not"; "The src layout helps prevent accidental usage of the in-development copy
  of the code"; and it "helps enforce that an editable installation is only able to
  import files that were meant to be importable" [2].
- The Scientific Python Development Guide's packaging tutorial instructs: "Within the
  package directory `example`, create subdirectories `src` ('source') and `src/example`
  for the source code", with `pyproject.toml` "placed in the root directory" [4].
- pyOpenSci: "We strongly suggest, but do not require, that you use the **src/**
  layout… This layout is also recommended in the PyPA packaging guide tutorial", while
  noting that NumPy, SciPy, pandas, xarray, and scikit-learn all use the flat layout and
  that "we recommend that you use the src/package layout if you are creating a new
  package" [9].
- Hatch's own `hatch new` generates `src/<pkg>/`, `tests/`, `LICENSE.txt`, `README.md`,
  `pyproject.toml` [16].

**Consensus for new packages: src layout, package dir named after the project, config
in root `pyproject.toml`.** Light-Router already conforms.

### 2.2 Tests

- pytest's "Good Integration Practices" supports two layouts. Tests outside the
  application code "might be useful if you have many functional tests or for other
  reasons want to keep tests separate from actual application code (often a good
  idea)"; benefits are that "Your tests can run against an installed version after
  executing `pip install .`" and against an editable install. With the default
  `prepend` import mode "it is **strongly** suggested to use a `src` layout", and "For
  new projects, we recommend to use `importlib` import mode" (`addopts =
  ["--import-mode=importlib"]`) [8].
- Inlined tests (`src/mypkg/tests/`) are only recommended "if you have direct relation
  between tests and application modules and want to distribute them along with your
  application" [8].
- pyOpenSci: in a src layout "tests are normally included at the same directory level
  as the `src/` folder"; "we do not recommend including tests as part of your package
  wheel by default"; and "we strongly discourage you from including data in your test
  suite directory. Rather, host your test data in a repository such as Figshare or
  Zenodo. Use a tool such as Pooch" [9].
- sp-repo-review (the Scientific Python guide's checklist) expects: a tests folder
  (PY005), pytest configuration in `pyproject.toml` including test paths (PP303), and a
  defined dev dependency group (PP006) [6].

### 2.3 Examples vs experiments / benchmarks

No packaging standard prescribes where experiment code lives; the closest evidence is
what mature scientific projects actually do (Section 3) plus the data-science template
convention:

- CCDS v2 generates `notebooks/` (exploration), `reports/` + `reports/figures/`
  (generated analysis), and `models/` for experiment artifacts. Their "Opinions" page
  states: "Notebooks are for exploration and communication, source files are for
  repetition… Source code is superior for replicability because it is more portable,
  can be tested more easily, and is easier to code review", and "Refactor the good
  parts into source code" [11].
- On experiment outputs, CCDS says the `models` folder "has been used to keep track of
  experiments, hyperparameter configurations, results, and model artifacts" and that
  experiment documentation should let you "identify the provenance of the data and the
  version of the code that the experiment used, as well as the metrics used to measure
  performance" [12].
- In the scientific Python world, "examples" specifically means a user-facing gallery
  of runnable scripts (scikit-learn `examples/`, xarray `doc/gallery/`), whereas
  performance/experiment code goes in `benchmarks/` or `asv_bench/` (Section 3).

### 2.4 Data and experiment outputs

- CCDS v2 structure: `data/external`, `data/interim`, `data/processed`, `data/raw`, with
  the note that "the number or names of these folders is less important than flow of
  data between them" [10]. Opinions: "raw data must be treated as immutable — it's okay
  to read and copy raw data to manipulate it into new outputs, but never okay to change
  it in place"; "by default, the `data/` folder is included in the `.gitignore file`";
  "GitHub currently warns you if files are over 50MB and rejects any files over
  100MB" [11].
- DVC's model: data lives in the workspace (conventionally `data/`), the data itself is
  gitignored, and small human-readable metadata files (`.dvc` files / `dvc.yaml` with
  checksums, metrics, and plots) are versioned in Git: "Now the *metadata about your
  data* is versioned alongside your source code, while the original data file was added
  to `.gitignore`" [20][21].
- pyOpenSci's rule for *test* data (not user data): keep it out of the package; host it
  externally and fetch it (Pooch/Zenodo/Figshare) [9].

### 2.5 Documentation

- Diátaxis: "Diátaxis identifies four distinct needs, and four corresponding forms of
  documentation — *tutorials*, *how-to guides*, *technical reference* and
  *explanation*. It places them in a systematic relationship, and proposes that
  documentation should itself be organised around the structures of those needs" [22].
  mkdocs-material's documentation explicitly builds on this framework.
- pyOpenSci: `docs/` is the "user-facing documentation website", at the same level as
  `src/`; the core community files — `CHANGELOG.md`, `CODE_OF_CONDUCT.md`,
  `CONTRIBUTING.md`, `LICENSE`, `README.md` — "live in the root of your project
  directory" [9].
- sp-repo-review PY004 simply expects "Has docs folder" [6].

### 2.6 ADRs

- Nygard's original article: "We will keep ADRs in the project repository under
  `doc/arch/adr-NNN.md`… ADRs will be numbered sequentially and monotonically. Numbers
  will not be reused… If a decision is reversed, we will keep the old one around, but
  mark it as superseded." Format: Title, Context, Decision, Status, Consequences;
  "The whole document should be one or two pages long" [13].
- MADR: "Create folder `docs/decisions` in your project"; file names follow
  `NNNN-title-with-dashes.md`; "Decisions are placed in the subfolder `decisions/` to
  keep them close to the documentation but also separate the decisions from other
  documentation." MADR explicitly does not enforce one location: "MADR does not enforce
  any repository or directory organization structure" [14].

### 2.7 Tooling and CI configuration

- uv: `pyproject.toml` identifies the project root; the `.venv` lives next to it and is
  not committed; the `uv.lock` "should be checked into version control, allowing for
  consistent and reproducible installations across machines" [15].
- Scientific Python guide: "The proper way to specify dependencies exclusively used for
  development tasks (such as pytest, ruff, packages for generating documentation, etc.)
  is to use dependency-groups" [5].
- sp-repo-review expects: `pyproject.toml` (PY001), README (PY002), LICENSE (PY003),
  docs folder (PY004), tests folder (PY005), pre-commit config (PY006), "an easy task
  runner (nox, tox, pixi, etc.)" (PY007), `.gitignore` (PY008), GitHub Actions config
  (GH100) [6].
- CCDS ships a root `Makefile` "with convenience commands like `make data` or `make
  train`" [10]; scikit-learn also keeps a root `Makefile` [18].

## 3. How real scientific Python projects do it

Top-level listings verified via the GitHub API (2026-09-30).

**numpy** ([17]): flat layout — `numpy/` package at root, `doc/` (not `docs/`),
`benchmarks/` containing an airspeed-velocity (asv) suite (`asv.conf.json`,
`benchmarks/`), plus `tools/`, `requirements/`, `pyproject.toml`. The benchmarks README
describes asv workflow and notes results are published to a separate "benchmark results
repository" (asv-numpy), keeping benchmark outputs out of the main repo.

**scikit-learn** ([18]): flat layout — `sklearn/`, `doc/`, `examples/` (the user-facing
example gallery that the docs build pulls in), and *two* benchmark directories:
`benchmarks/` holding ad-hoc runnable scripts (`bench_*.py`, e.g. `bench_pca_solvers.py`,
`bench_plot_lasso_path.py` that produce timings/plots) and `asv_benchmarks/` for the
asv regression suite. Also `maint_tools/`, `build_tools/`, root `Makefile`,
`.binder/`, `CITATION.cff`, `CONTRIBUTING.md`, `SECURITY.md` at root.

**xarray** ([19]): flat layout — `xarray/`, `doc/` with `doc/examples/` and
`doc/gallery/` (example notebooks live *inside* the docs tree; the old top-level
`examples/` directory is now empty), `asv_bench/`, `design_notes/`, `ci/`,
`properties/`, plus `CONTRIBUTING.md`, `CITATION.cff`, `HOW_TO_RELEASE.md` at root.

Patterns worth copying:

- Benchmarks/experiment scripts are separated from user-facing examples, and each has
  a dedicated top-level directory (`benchmarks/`, `asv_benchmarks/`, `asv_bench/`).
- User-facing examples either get `examples/` (scikit-learn) or move into the docs
  tree as a gallery (xarray).
- Heavy benchmark *results* are published to a separate location, not committed
  (numpy's asv results repo).
- Community files (CONTRIBUTING, CITATION, SECURITY) sit at the repo root.
- All three use the flat layout for historical reasons — pyOpenSci explicitly calls
  this out as not worth migrating for established packages, while recommending src for
  new ones [9].

## 4. Recommended target structure for Light-Router

```
Light-Router/
├── AGENTS.md
├── LICENSE
├── README.md
├── CONTRIBUTING.md          # MOVE from docs/CONTRIBUTING.md
├── Makefile                 # keep
├── mkdocs.yml               # keep
├── pyproject.toml           # keep (pytest config stays here)
├── uv.lock                  # keep, committed
├── .github/workflows/       # keep
├── src/light_router/        # keep unchanged
├── tests/                   # keep flat, at root
├── experiments/             # RENAME from examples/
│   ├── degradation_curve.py
│   └── operational_passage.py
├── data/                    # keep gitignored
│   ├── cache/               # regenerable fetch cache (interim-like)
│   └── packs/               # immutable checksummed inputs (raw-like)
├── runs/                    # keep gitignored experiment outputs
├── docs/                    # user-facing site, reorganized per Diátaxis
│   ├── index.md, about.md
│   ├── tutorials/ how-to/ reference/ explanation/   # see 4.5
│   ├── adr/                 # keep (ADR-NNNN-*.md)
│   └── agents/              # keep, but see 4.6
└── specs/                   # keep (Notion mirrors)
```

### 4.1 Keep: src layout, root pyproject, uv, dependency-groups

Already matches every standard: PyPA [1][2], the Scientific Python guide [4][5],
pyOpenSci [9], Hatch [16], uv [15]. `uv.lock` committed per uv docs [15]; dev/docs/
grib/artifacts/plot groups per the guide's dependency-groups recommendation [5] and
sp-repo-review PP006 [6]. No change.

### 4.2 Keep: tests/ flat at root

Matches pytest's recommended "tests outside application code" layout with src layout
[8], pyOpenSci [9], and sp-repo-review PY005/PP303 [6] (`testpaths = ["tests"]` is
already set). Two cheap improvements from the same sources: add
`--import-mode=importlib` ("we recommend [it] for new projects" [8]), and keep any
large test fixtures out of the tree — host externally and fetch, per pyOpenSci's
Pooch/Zenodo guidance [9] (the checksummed `data/packs` already serve this role).

### 4.3 Rename: examples/ → experiments/

`degradation_curve.py` and `operational_passage.py` are the project's actual
experiments, not user-facing examples. In the scientific Python convention "examples"
means a documentation gallery (scikit-learn `examples/` [18], xarray `doc/gallery/`
[19]); experiment/benchmark drivers get their own top-level directory (scikit-learn
`benchmarks/` [18], numpy `benchmarks/` [17], xarray `asv_bench/` [19]). Renaming to
`experiments/` (a) stops the directory from promising a gallery it doesn't contain, and
(b) matches the case-study pattern of dedicated experiment directories. This also
aligns with CCDS's opinion that repeatable analysis belongs in source files, not
notebooks [11]. If a user-facing gallery is added later, it should go under `docs/`
(xarray style) or a true `examples/` with docs links.

### 4.4 Keep: data/ and runs/ gitignored, with explicit subfolder semantics

The current scheme already implements the two strongest data conventions:

- "by default, the `data/` folder is included in the `.gitignore`" (CCDS [11]); the
  2.4 GB GRIB cache must stay out of Git (GitHub rejects files over 100 MB [11]).
- DVC's core pattern — data outside Git, checksummed metadata inside [20][21] — is
  what `data/packs` (29 MB, checksummed) already does without DVC itself.

Recommended refinement: document the flow semantics CCDS prescribes — `data/packs` is
immutable raw input ("never okay to change it in place" [11]), `data/cache` is
regenerable interim storage, `runs/` is generated output (CCDS `reports/`/`models/`
analog). CCDS explicitly blesses custom names: "the number or names of these folders is
less important than flow of data between them" [10]. Each `runs/` manifest should keep
recording data provenance + code version + metrics, which is exactly CCDS's minimum for
experiment documentation [12].

### 4.5 Reorganize docs/ content per Diátaxis

The current flat `docs/*.md` mix (index, about, objectives, benchmarking,
routing-algorithms, market-positioning, literature-review, research-ideas,
meteorological-info-transfer, PROJECT_DESCRIPTION) mixes user-facing material with
internal research notes. Diátaxis — the framework mkdocs-material is built around —
says documentation "should itself be organised around" the four forms: tutorials,
how-to guides, reference, explanation [22]. Suggested mapping:

- Tutorials / how-to: `benchmarking.md`, operational usage of the passage example.
- Reference: API pages (currently absent; mkdocstrings would live here).
- Explanation: `routing-algorithms.md`, `meteorological-info-transfer.md`.
- Move *internal* notes (`literature-review.md`, `research-ideas.md`,
  `market-positioning.md`, `PROJECT_DESCRIPTION.md`, `objectives.md`) out of
  user-facing `docs/` — e.g. to `specs/` or a `research/` directory. This is also
  required by this repo's own AGENTS.md ("docs/ is user-facing only").

### 4.6 Move CONTRIBUTING.md to the root

pyOpenSci places CONTRIBUTING among the root community files [9]; scikit-learn and
xarray both keep `CONTRIBUTING.md` at root [18][19]. GitHub also surfaces root
CONTRIBUTING in its UI. Low-cost, standard-aligning move.

### 4.7 Keep: docs/adr/ with ADR-NNNN naming

`docs/adr/ADR-0001-npz-data-packs.md` matches MADR's `NNNN-title-with-dashes.md`
pattern and its placement advice ("close to the documentation but also separate" [14]).
Nygard's original `doc/arch/adr-NNN.md` differs [13], but MADR explicitly does not
enforce a location [14]. Keep the sequential numbering and Nygard's superseded-not-
deleted rule [13].

### 4.8 Keep: Makefile, .github/workflows, mkdocs.yml, AGENTS.md, specs/

Makefile as task runner satisfies sp-repo-review PY007 [6] and mirrors CCDS [10] and
scikit-learn [18]. GitHub Actions config satisfies GH100 [6]. `specs/` has no
analog in any standard — see 5.

## 5. Where standards disagree, and justified deviations

- **src vs flat layout.** The five biggest scientific packages use flat layout; PyPA,
  the Scientific Python guide, pyOpenSci, and Hatch all recommend src for *new*
  packages [2][4][9][16]. pyOpenSci resolves the tension explicitly: flat is legacy
  inertia, src is right for new projects [9]. Light-Router is new and already src —
  no action.
- **Tests inside vs outside the package.** Both are sanctioned [8]; the choice depends
  on whether tests ship with the wheel. Light-Router does not ship tests, so outside-
  layout is correct [8][9].
- **ADR location.** Nygard says `doc/arch/` [13], MADR says `docs/decisions/` [14];
  MADR allows any structure. Light-Router's `docs/adr/` is a legitimate hybrid.
- **"Examples" semantics.** Standards are silent on experiment code; the convention
  borrowed from numpy/scikit-learn/xarray treats `examples/` as user-facing gallery
  content [17][18][19]. Light-Router's scripts are experiments, hence the rename in
  4.3 — a deviation from the *name*, justified by the *content*.
- **Justified deviation — experiments as first-class citizens.** No packaging
  standard (PyPA, Scientific Python guide, pyOpenSci) models experiment drivers, run
  outputs, or data packs; the CCDS data-science template is the closest analog but
  assumes notebooks + a flat module and is not a packaging standard [10][11].
  Light-Router's `experiments/ + data/packs + runs/` triad is a reasonable synthesis of
  CCDS's DAG/immutability opinions [11], CCDS's experiment-provenance minimum [12], and
  DVC's metadata-in-git/data-out-of-git pattern [21], without adopting DVC itself.
- **Justified deviation — Notion as spec source of truth.** `specs/` mirrors exist only
  for PR review (per AGENTS.md). No standard covers this; it is a deliberate
  workflow choice and should stay, but the mirrors should stay clearly marked as
  non-canonical to avoid drift with the Notion pages.
- **Tension to resolve — docs/agents/ inside user-facing docs/.** AGENTS.md says
  "docs/ is user-facing only", yet `docs/agents/` (agent instructions) and internal
  research notes live there. Either move `docs/agents/` to the repo root (next to
  AGENTS.md, which is where agents look first) or accept the exception explicitly.
  sp-repo-review only requires that *a* docs folder exists [6], so either is
  standard-compatible.
- **Minor hygiene:** `examples/output/` and `examples/__pycache__/` should be
  gitignored (they appear to be already) and the build output `site/` stays ignored
  [15]-adjacent; numpy keeps benchmark results in a separate repository [17], which
  supports keeping `runs/` unversioned.
