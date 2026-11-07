# arrow-mapper

Atlas formatter and previewer. Detect sprite regions, fit replacement artwork
into an existing sheet, and export a PNG with Sparrow XML, numbered previews,
and comparison overlays. Python 3.15 or newer is required.

## Install

Clone this repository and install the locked dependencies:

```sh
git clone https://github.com/philosolog/arrow-mapper.git
cd arrow-mapper
uv sync --locked
uv run python constructor.py --help
```

## Use your own artwork

`sources/layout/map.png` is included as the reusable layout template. To use it
with your own replacement image:

```sh
mkdir -p local
# Supply local/arrow.png first.
uv run python constructor.py detect --sheet sources/layout/map.png --source local/arrow.png --recipe local/recipe.json
uv run python constructor.py build --recipe local/recipe.json --output output/atlas.png
```

Put your sheet and replacement images in `local/`. This directory is gitignored.
Detect a layout with one or more replacement images:

```sh
mkdir -p local
# Supply local/sheet.png and local/arrow.png first.
uv run python constructor.py detect --sheet local/sheet.png --source local/arrow.png --recipe local/recipe.json
uv run python constructor.py build --recipe local/recipe.json --output output/atlas.png
```

Repeat `--source` to include more replacement images. Detection writes a recipe
and a numbered preview. It refuses to overwrite an existing recipe.
Review region boxes, names, and replacement choices before building. Connected
components can merge touching sprites or split disconnected artwork. Detection
cannot recover original animation names or frame offsets.

Build exports PNG, XML, numbered preview, comparison overlay, and match scores.
Image paths in recipes resolve relative to the recipe file. Detection records
absolute input paths; change them to relative paths when moving your data.

Recipes contain `sheet`, `sources`, and `regions`. Each region has `box`
(`[x, y, width, height]`), `name`, and `replace`. Replacement regions also use
`source` (a listed path or `"auto"`), `rotation` (degrees or `"auto"`), `flip`
(`"none"`, `"horizontal"`, `"vertical"`, or `"auto"`), and `recolor`
(`"none"`, `"target"`, or a color such as `"#c24b99"`). Optional `frameX`,
`frameY`, `frameWidth`, and `frameHeight` preserve engine offsets.

## Tests and local content

```sh
uv run python -m unittest discover -s tests
```

Tests generate their own temporary artwork. No personal assets are required.
Existing artwork, root PNGs, root recipes, `sources/` except the map template, `output/`, `local/`, and
the upload-specific `tools/extract_black_keys.py` are ignored and remain on disk.
Existing design notes and asset-dependent tests live in `local/`. Run those
optional tests from the repository root with
`uv run python -m unittest discover -s local/tests` after building their outputs.

Gitignore does not remove files already tracked by Git or erase old commits.
Review staged paths before publishing. Back up ignored artwork separately;
cloning this repository will not restore it.
