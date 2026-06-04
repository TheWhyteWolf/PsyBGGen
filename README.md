# PsyGenADV

A command-line tool for generating randomised psychedelic background images by combining geometric patterns with spatial distortions. Outputs greyscale PNGs suitable for use as textures, wallpapers, stage backdrops, or generative art source material.

---

## Features

- **8 base patterns** — from classic chessboards and concentric rings to Voronoi cells, Truchet tiles, moiré grids, and organic plasma fields
- **9 distortion effects** — ripple, swirl, fisheye, domain warp, multi-swirl, polar fold, shear wave, and more
- Randomised combinations with a seeded RNG so any output is fully reproducible
- Zoom controls to independently scale pattern density and distortion intensity
- Pure NumPy/Pillow — no deep learning, no internet, no GPU required

---

## Requirements

- Python 3.8+
- NumPy
- Pillow

Install dependencies:

```bash
pip install numpy pillow
```

---

## Usage

```bash
python PsyGenADV.py [options]
```

### Options

| Flag | Default | Description |
|---|---|---|
| `-n, --count` | `10` | Number of images to generate |
| `-s, --size` | `1024` | Output image size in pixels (square) |
| `-o, --output` | `./backgrounds` | Output directory (created if absent) |
| `-p, --pattern` | random | Force a specific base pattern |
| `-d, --distortion` | random | Force a specific distortion |
| `--pzoom`, `--zoom` | `1.0` | Zoom factor for pattern features (`--zoom` is a legacy alias) |
| `--dzoom` | `1.0` | Zoom factor for distortion features |

`--pzoom` and `--dzoom` are independent and can be combined freely.

### Examples

Generate 20 random images at 2048×2048:

```bash
python PsyGenADV.py -n 20 -s 2048
```

Generate 5 images using chessboard + swirl:

```bash
python PsyGenADV.py -n 5 -p chessboard -d swirl
```

Increase pattern density (finer features):

```bash
python PsyGenADV.py -n 10 --zoom 2.5
```

Coarsen the pattern but keep distortion subtle, or scale each independently:

```bash
python PsyGenADV.py -n 10 --pzoom 0.5 --dzoom 3.0
```

---

## Available Patterns

| Name | Description |
|---|---|
| `chessboard` | Alternating square tiles |
| `stripes` | Rotated parallel bands at a random angle |
| `circles` | Concentric rings from a random centre |
| `plasma` | Overlapping sine wave interference — classic demoscene gradient |
| `sunburst` | Alternating wedges radiating from a centre point |
| `voronoi` | Even/odd nearest-cell colouring — cracked glass look |
| `moire` | Two ring grids at slightly different frequencies producing large-scale beating |
| `truchet` | Randomised quarter-circle arc tiles forming maze-like curves |

## Available Distortions

| Name | Description |
|---|---|
| `ripple` | Orthogonal sine-wave displacement |
| `grid` | Smooth random vector field applied over a coarse grid |
| `warp` | Multi-octave sine warp — organic turbulence |
| `swirl` | Single-centre spiral rotation |
| `polar` | Folds the image into polar coordinates with optional radial twist |
| `fisheye` | Radial lens distortion — bulge or pinch |
| `multiswirl` | Several independent swirl centres — chaotic and turbulent |
| `domainwarp` | Iterative self-referential warp (Inigo Quilez technique) — fractal-like |
| `shear` | Row or column offset by a sine wave — venetian-blind ripple |

---

## Output

Images are saved as greyscale PNGs with filenames encoding the generation parameters:

```
bg_001_plasma_domainwarp_seed827364591.png
```

The seed value embedded in each filename can be used to reproduce any result exactly by re-seeding NumPy and Python's `random` module to the same value before calling the pattern and distortion functions directly.

---

## Licence

MIT
