# Agent instructions

## Scope and editing rules

This repository provides a reusable sprite-sheet constructor. Keep the public
code usable on a fresh clone without any personal artwork or saved recipes.

- Read a file before editing it. Search all callers before modifying a function.
- Investigate existing behavior before editing. Reuse existing helpers and keep
  changes scoped to the request.
- Do not read or search `build/`, `node_modules/`, `.git/`, `dist/`, or
  `__pycache__/` unless the user explicitly asks.
- Keep responses concise. State what changed, what was verified, and any limits.

## Repository map

- `constructor.py`: CLI and shared image loading, detection, fitting, preview,
  and atlas export functions.
- `pyproject.toml` and `uv.lock`: Python requirements and locked dependencies.
- `tests/test_cli.py`: synthetic CLI test requiring no personal assets.
- `README.md`: installation, usage, and recipe format.
- `sources/layout/map.png`: tracked, reusable layout template. Keep it available
  on fresh clones; other files in `sources/` remain private and ignored.
- Ignored `local/`, `sources/`, root PNGs and recipes, and `output/`: user data
  and generated files. These may be absent on a fresh clone.
- Ignored `tools/extract_black_keys.py` and `local/tests/`: legacy tools and
  checks for specific artwork. They are optional, not public prerequisites.

## Setup and workflow

Run commands from the repository root. Python 3.15 or newer and uv are required.

```sh
uv sync --locked
uv run python constructor.py --help
```

Use the user's supplied sheet and replacement artwork. Store new inputs and
recipes in `local/`, and generated atlases in `output/`. Do not assume example
paths exist or substitute old personal assets for missing inputs.

```sh
mkdir -p local
# The user must supply these images before detection.
uv run python constructor.py detect --sheet local/sheet.png --source local/arrow.png --recipe local/recipe.json
uv run python constructor.py build --recipe local/recipe.json --output output/atlas.png
```

Repeat `--source` for multiple replacement images. Detection creates a recipe
and numbered preview, and refuses to overwrite an existing recipe. To revise
an existing recipe, read and edit it or detect into a new filename.

Review detected boxes, frame names, replacement choices, and the preview before
using a build. Detection uses connected components; touching sprites may merge
and disconnected artwork may split. Original animation names and frame offsets
cannot be recovered from pixels. Preserve supplied XML names and offsets when
the user needs compatibility with an existing engine atlas.

Image paths resolve relative to the recipe file. Detection writes absolute
input paths. When making a recipe portable, update `sheet`, `sources`, and all
region source references consistently. Consult `README.md` and `fit()` for
supported recipe fields rather than inventing new ones.

Build requires both `--recipe` and `--output`. It writes PNG, Sparrow XML,
numbered preview, comparison overlay, and match scores beside the output PNG.
Use a new output basename if existing results must be retained. Never use an
input image as the output path.

## Data boundaries

- Preserve local artwork and recipes unless the user requests changes.
- Do not force-add ignored files or embed personal paths or artwork in public
  code, documentation, fixtures, or tests.
- Keep public tests self-contained using temporary, generated artwork.
- Do not restore hardcoded red/grey builds or dependencies on `sources/`.
- Before publishing, inspect staged paths using Git commands. Gitignore does
  not untrack existing files or erase history. Do not rewrite history without
  an explicit request.
- Ignored assets need separate backups; a GitHub clone will not restore them.

## Verification

For changes to public behavior, run:

```sh
uv run python -m unittest discover -s tests
```

Add a small synthetic check for new nontrivial behavior. Verify changes without
private local artwork when claiming fresh-clone compatibility. Do not require private
fixtures to pass the public suite.

Run `uv run python -m unittest discover -s local/tests` only when the relevant
local assets and built outputs exist and the task affects those designs.
Inspect generated previews when changing rendering. Report engine playback as
unverified unless it was actually checked in the target engine.
