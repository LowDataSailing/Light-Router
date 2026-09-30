# Contributing

## How to Contribute
- Report bugs via GitHub Issues
- Suggest features via GitHub Issues
- Submit pull requests
- Improve documentation

## Setup
```bash
git clone https://github.com/LowDataSailing/Light-Router.git
cd Light-Router
uv sync --all-groups
```

## Code Style
- Follow PEP 8
- Use Ruff for formatting (`make format`)
- Type hints for all function signatures
- Google-style docstrings

## Testing
```bash
make test
```

## Repository Layout

```
Light-Router/
├── src/light_router/   # the package (models, routing, harness, simulation,
│                       #  weather_data, reporting)
├── tests/              # pytest suite
├── experiments/        # runnable experiment drivers (the Goal 1 experiments)
├── data/               # gitignored: packs/ = immutable checksummed experiment
│                       # inputs; cache/ = regenerable fetch cache
├── runs/               # gitignored: experiment output directories
├── specs/              # working mirrors of the Notion specs (for PR review)
├── research/           # internal research notes (not on the docs site)
├── docs/               # user-facing documentation site (mkdocs)
└── agents/             # agent instructions (issue tracker, triage, domain)
```

Data flow: `data/packs/` is immutable raw input (never modified in place —
verify checksums, don't edit); `data/cache/` is regenerable interim storage
(safe to delete; re-fetching rebuilds it); `runs/` is generated output
(regenerate with the experiment's `--artifacts` flag or from a data pack).
Heavy data never enters git.
