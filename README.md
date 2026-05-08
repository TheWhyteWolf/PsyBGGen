# PsyBGGen

Procedurally generates randomised black-and-white background images by combining geometric patterns with image distortions.

## Requirements


pip install numpy pillow


## Usage


python PsyBGGen.py [OPTIONS]


| Flag | Default | Description |
|---|---|---|
| `-n`, `--count` | `10` | Number of images to generate |
| `-s`, `--size` | `1024` | Image size in pixels (square) |
| `-o`, `--output` | `./backgrounds` | Output directory |
| `-p`, `--pattern` | *(random)* | `chessboard`, `stripes`, or `circles` |
| `-d`, `--distortion` | *(random)* | `ripple`, `grid`, `warp`, or `swirl` |
| `--zoom` | `1.0` | Scale pattern feature size |
| `--zoomall` | `1.0` | Scale pattern and distortion feature sizes |

`--zoom` and `--zoomall` are mutually exclusive.

## Examples


# 20 random images at 512×512
python PsyBGGen.py -n 20 -s 512

# Force a specific combination
python PsyBGGen.py -p chessboard -d swirl

# Finer-grained features
python PsyBGGen.py --zoom 2.0


## Output

Greyscale PNGs saved to the output directory. Filenames include the random seed so any result can be reproduced:

```
backgrounds/
├── bg_001_seed174392810.png
├── bg_002_seed908123447.png
└── ...
```

## Licence

GNU 3
