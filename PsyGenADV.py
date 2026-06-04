import argparse
import random
import math
from pathlib import Path
import numpy as np
from PIL import Image

def remap_image(img, map_x, map_y):
    """Bilinear interpolation to warp the image smoothly."""
    size = img.shape[0]
    map_x = np.clip(map_x, 0, size - 1)
    map_y = np.clip(map_y, 0, size - 1)

    x0, y0 = np.floor(map_x).astype(int), np.floor(map_y).astype(int)
    x1, y1 = np.minimum(x0 + 1, size - 1), np.minimum(y0 + 1, size - 1)

    fx, fy = map_x - x0, map_y - y0

    return (
        img[y0, x0] * (1 - fx) * (1 - fy) +
        img[y0, x1] * fx * (1 - fy) +
        img[y1, x0] * (1 - fx) * fy +
        img[y1, x1] * fx * fy
    ).astype(np.uint8)
def binarize(arr, threshold=128):
    return np.where(arr >= threshold, 255, 0).astype(np.uint8)
# =============================================================================
# PATTERNS
# =============================================================================

def chessboard(size, zoom=1.0, tile_size=None):
    if not tile_size:
        lo = max(1, int((size // 16) / zoom))
        hi = max(lo + 1, int((size // 6) / zoom))
        tile_size = random.randint(lo, hi)

    x, y = np.meshgrid(np.arange(size), np.arange(size))
    grid = ((x // tile_size) + (y // tile_size)) % 2
    return (grid * 255).astype(np.uint8)


def stripes(size, zoom=1.0, width=None, angle=None):
    if not width:
        lo = max(1, int((size // 20) / zoom))
        hi = max(lo + 1, int((size // 6) / zoom))
        width = random.randint(lo, hi)

    angle = angle if angle is not None else random.uniform(0, 180)
    rad = math.radians(angle)

    x, y = np.meshgrid(np.arange(size) - size / 2, np.arange(size) - size / 2)
    projected = x * math.cos(rad) + y * math.sin(rad)

    grid = np.abs((projected // width) % 2).astype(int)
    return (grid * 255).astype(np.uint8)


def concentric_circles(size, zoom=1.0, ring_width=None, cx=None, cy=None):
    if not ring_width:
        lo = max(1, int((size // 20) / zoom))
        hi = max(lo + 1, int((size // 8) / zoom))
        ring_width = random.randint(lo, hi)

    cx = cx or random.uniform(0.3, 0.7) * size
    cy = cy or random.uniform(0.3, 0.7) * size

    x, y = np.meshgrid(np.arange(size, dtype=float) - cx, np.arange(size, dtype=float) - cy)
    dist = np.sqrt(x**2 + y**2)

    grid = (dist // ring_width) % 2
    return (grid * 255).astype(np.uint8)


def plasma(size, zoom=1.0):
    """Smooth organic gradients from overlapping sine waves — classic demoscene effect."""
    x, y = np.meshgrid(np.linspace(0, 4 * zoom, size), np.linspace(0, 4 * zoom, size))
    cx = random.uniform(1, 3) * zoom
    cy = random.uniform(1, 3) * zoom
    r = np.sqrt((x - cx)**2 + (y - cy)**2)
    v = (np.sin(x) + np.sin(y) + np.sin(x + y) + np.sin(r)) / 4
    return binarize(((v + 1) / 2 * 255).astype(np.uint8))

def sunburst(size, zoom=1.0, spokes=None):
    """Alternating wedges radiating from a centre point."""
    spokes = spokes or random.randint(6, 24)
    cx, cy = size / 2, size / 2
    x, y = np.meshgrid(np.arange(size, dtype=float) - cx, np.arange(size, dtype=float) - cy)
    angle = np.arctan2(y, x)  # -π to π
    sector = (angle / (2 * math.pi) * spokes * zoom) % 2
    return (sector.astype(int) * 255).astype(np.uint8)


def voronoi(size, zoom=1.0, n_points=None):
    """Even/odd nearest-cell colouring — cracked glass or stained glass look."""
    n_points = n_points or random.randint(10, 40)
    pts = np.random.rand(n_points, 2) * size
    x, y = np.meshgrid(np.arange(size), np.arange(size))
    coords = np.stack([y, x], axis=-1).reshape(-1, 2)      # (size², 2)
    diffs = coords[:, None, :] - pts[None, :, :]           # (size², n, 2)
    dists = np.linalg.norm(diffs, axis=-1)
    nearest = np.argmin(dists, axis=-1).reshape(size, size)
    return ((nearest % 2) * 255).astype(np.uint8)


def moire(size, zoom=1.0, freq1=None, freq2=None):
    """Two overlapping concentric ring grids at slightly different frequencies.
    The beating between them generates large-scale moiré patterns automatically."""
    freq1 = (freq1 or random.uniform(8, 20)) * zoom
    freq2 = freq1 * random.uniform(1.02, 1.12)             # slight offset is the key
    x, y = np.meshgrid(np.arange(size, dtype=float), np.arange(size, dtype=float))
    r1 = np.sqrt((x - size / 2)**2 + (y - size / 2)**2)
    r2 = np.sqrt((x - size * 0.55)**2 + (y - size * 0.45)**2)
    v = np.sin(r1 * freq1 / size * 2 * math.pi) * np.sin(r2 * freq2 / size * 2 * math.pi)
    return binarize(((v + 1) / 2 * 255).astype(np.uint8))


def truchet(size, zoom=1.0, tile_size=None):
    """Randomised quarter-circle arc tiles that chain into flowing, maze-like curves."""
    tile_size = max(8, int(size // (12 * zoom)))
    # Build one-pixel arc masks for each tile orientation
    t = tile_size
    tl = np.arange(t, dtype=float)
    tx, ty = np.meshgrid(tl, tl)
    nx, ny = tx / t - 0.5, ty / t - 0.5

    # Two possible arcs: bottom-left corner vs. top-right corner
    d0 = np.abs(np.sqrt(nx**2 + ny**2) - 0.5) < 0.1          # arc from top-left
    d1 = np.abs(np.sqrt((nx - 1)**2 + (ny - 1)**2) - 0.5) < 0.1  # arc from bottom-right

    img = np.zeros((size, size), dtype=np.uint8)
    for row in range(0, size, t):
        for col in range(0, size, t):
            mask = d1 if random.random() > 0.5 else d0
            r_end = min(row + t, size)
            c_end = min(col + t, size)
            img[row:r_end, col:c_end] = (mask[:r_end - row, :c_end - col] * 255)
    return img


PATTERNS = {
    'chessboard': chessboard,
    'stripes': stripes,
    'circles': concentric_circles,
    'plasma': plasma,
    'sunburst': sunburst,
    'voronoi': voronoi,
    'moire': moire,
    'truchet': truchet,
}

# =============================================================================
# DISTORTIONS
# =============================================================================

def ripple(img, zoom=1.0, strength=None, freq=None):
    size = img.shape[0]
    strength = strength or random.uniform(size * 0.01, size * 0.04)
    freq = (freq or random.uniform(2, 8)) * zoom

    x, y = np.meshgrid(np.arange(size, dtype=float), np.arange(size, dtype=float))
    dx = strength * np.sin(2 * math.pi * freq * y / size)
    dy = strength * np.sin(2 * math.pi * freq * x / size)

    return remap_image(img, x + dx, y + dy)


def grid_displacement(img, zoom=1.0, cells=None, strength=None):
    size = img.shape[0]
    cells = max(2, int((cells or random.randint(4, 12)) * zoom))
    strength = (strength or random.uniform(size * 0.02, size * 0.06)) / zoom

    noise_x = (np.random.rand(cells + 3, cells + 3) - 0.5) * 2 * strength
    noise_y = (np.random.rand(cells + 3, cells + 3) - 0.5) * 2 * strength

    dx = np.array(Image.fromarray(noise_x.astype(np.float32)).resize((size, size), Image.BICUBIC))
    dy = np.array(Image.fromarray(noise_y.astype(np.float32)).resize((size, size), Image.BICUBIC))

    x, y = np.meshgrid(np.arange(size, dtype=float), np.arange(size, dtype=float))
    return remap_image(img, x + dx, y + dy)


def warp(img, zoom=1.0, strength=None, octaves=3):
    size = img.shape[0]
    strength = (strength or random.uniform(size * 0.05, size * 0.15)) / zoom

    x, y = np.meshgrid(np.arange(size, dtype=float) / size, np.arange(size, dtype=float) / size)
    dx, dy = np.zeros_like(x), np.zeros_like(y)

    for i in range(1, octaves + 1):
        freq = (2 ** i) * zoom
        a1, a2, a3, a4 = [random.uniform(0, 2 * math.pi) for _ in range(4)]
        dx += (1 / i) * np.sin(freq * math.pi * y + a1) * np.cos(freq * math.pi * x + a2)
        dy += (1 / i) * np.cos(freq * math.pi * x + a3) * np.sin(freq * math.pi * y + a4)

    map_x = np.clip((x + dx * strength / size) * size, 0, size - 1)
    map_y = np.clip((y + dy * strength / size) * size, 0, size - 1)

    return remap_image(img, map_x, map_y)


def swirl(img, zoom=1.0, angle=None, radius=None):
    size = img.shape[0]
    angle = angle or random.uniform(math.pi * 0.5, math.pi * 2)
    radius = (radius or random.uniform(size * 0.2, size * 0.6)) / zoom

    cx, cy = size / 2, size / 2
    x, y = np.meshgrid(np.arange(size, dtype=float) - cx, np.arange(size, dtype=float) - cy)
    r = np.sqrt(x**2 + y**2)

    theta = np.arctan2(y, x) + angle * np.exp(-r / radius)
    src_x = cx + r * np.cos(theta)
    src_y = cy + r * np.sin(theta)

    return remap_image(img, src_x, src_y)


def polar_warp(img, zoom=1.0, twist=None):
    """Folds the image into polar coordinates, creating a radial tunnel effect.
    An optional twist rotates pixels proportionally to their distance from centre."""
    size = img.shape[0]
    twist = twist if twist is not None else random.uniform(-2.0, 2.0)
    cx, cy = size / 2, size / 2
    x, y = np.meshgrid(np.arange(size, dtype=float) - cx, np.arange(size, dtype=float) - cy)
    r = np.sqrt(x**2 + y**2) / (size / 2)             # normalised 0–1
    theta = np.arctan2(y, x) + twist * r              # optional radial twist
    src_x = cx + (theta / (2 * math.pi)) * size
    src_y = cy + r * (size / 2)
    return remap_image(img, src_x % size, np.clip(src_y, 0, size - 1))


def fisheye(img, zoom=1.0, strength=None):
    """Radial lens distortion. Positive strength = bulge outward; negative = pinch inward."""
    size = img.shape[0]
    strength = strength or random.uniform(0.3, 1.5) * random.choice([-1, 1])
    cx, cy = size / 2, size / 2
    x, y = np.meshgrid(np.arange(size, dtype=float) - cx, np.arange(size, dtype=float) - cy)
    r_norm = np.sqrt(x**2 + y**2) / (size / 2)
    factor = np.where(
        r_norm == 0, 1.0,
        np.arctan(strength * r_norm) / (strength * r_norm + 1e-9)
    )
    return remap_image(img, cx + x * factor, cy + y * factor)


def multi_swirl(img, zoom=1.0, n_centres=None):
    """Several independent swirl centres fighting each other — turbulent and chaotic."""
    size = img.shape[0]
    n_centres = n_centres or random.randint(2, 5)
    x, y = np.meshgrid(np.arange(size, dtype=float), np.arange(size, dtype=float))
    src_x, src_y = x.copy(), y.copy()
    for _ in range(n_centres):
        cx = random.uniform(0.2, 0.8) * size
        cy = random.uniform(0.2, 0.8) * size
        angle = random.uniform(math.pi * 0.5, math.pi * 1.5) * random.choice([-1, 1])
        radius = random.uniform(size * 0.15, size * 0.4) / zoom
        dx, dy = src_x - cx, src_y - cy
        r = np.sqrt(dx**2 + dy**2)
        theta = np.arctan2(dy, dx) + angle * np.exp(-r / radius)
        src_x = cx + r * np.cos(theta)
        src_y = cy + r * np.sin(theta)
    return remap_image(img, src_x, src_y)


def domain_warp(img, zoom=1.0, iterations=None, strength=None):
    """Applies warp distortion to its own output coordinates iteratively.
    The self-referential feedback creates fractal-like turbulence (Inigo Quilez technique)."""
    size = img.shape[0]
    iterations = iterations or random.randint(2, 3)
    strength = (strength or random.uniform(size * 0.05, size * 0.12)) / zoom
    x, y = np.meshgrid(np.arange(size, dtype=float), np.arange(size, dtype=float))
    qx, qy = x / size, y / size
    for _ in range(iterations):
        a1, a2 = random.uniform(0, 2 * math.pi), random.uniform(0, 2 * math.pi)
        freq = random.uniform(1.5, 4.0) * zoom
        nx = np.sin(freq * math.pi * qy + a1) * np.cos(freq * math.pi * qx + a2)
        ny = np.cos(freq * math.pi * qx + a1) * np.sin(freq * math.pi * qy + a2)
        qx = qx + nx * strength / size
        qy = qy + ny * strength / size
    return remap_image(img, np.clip(qx * size, 0, size - 1), np.clip(qy * size, 0, size - 1))


def shear_wave(img, zoom=1.0, strength=None, freq=None):
    """Rows or columns offset by a smoothly varying sine — a rippling venetian-blind effect."""
    size = img.shape[0]
    strength = strength or random.uniform(size * 0.02, size * 0.08)
    freq = (freq or random.uniform(1, 5)) * zoom
    x, y = np.meshgrid(np.arange(size, dtype=float), np.arange(size, dtype=float))
    phase = random.uniform(0, math.pi)
    if random.random() > 0.5:
        dx = strength * np.sin(2 * math.pi * freq * y / size + phase)
        return remap_image(img, x + dx, y)
    else:
        dy = strength * np.sin(2 * math.pi * freq * x / size + phase)
        return remap_image(img, x, y + dy)


DISTORTIONS = {
    'ripple': ripple,
    'grid': grid_displacement,
    'warp': warp,
    'swirl': swirl,
    'polar': polar_warp,
    'fisheye': fisheye,
    'multiswirl': multi_swirl,
    'domainwarp': domain_warp,
    'shear': shear_wave,
}

# =============================================================================
# MAIN PIPELINE
# =============================================================================

def generate_batch(count, size, out_dir, p_name=None, d_name=None, p_zoom=1.0, d_zoom=1.0):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, count + 1):
        seed = random.randint(0, 2**31)
        random.seed(seed)
        np.random.seed(seed)

        pattern_name  = p_name or random.choice(list(PATTERNS.keys()))
        distort_name  = d_name or random.choice(list(DISTORTIONS.keys()))
        pattern_func  = PATTERNS[pattern_name]
        distort_func  = DISTORTIONS[distort_name]

        arr = pattern_func(size, zoom=p_zoom)
        arr = distort_func(arr, zoom=d_zoom)

        filename = out_dir / f"bg_{i:03d}_{pattern_name}_{distort_name}_seed{seed}.png"
        Image.fromarray(arr, mode='L').save(filename)
        print(f"Saved {i}/{count} -> {filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate randomized psychedelic background patterns.")
    parser.add_argument("-n", "--count",      type=int, default=10,           help="Number of images")
    parser.add_argument("-s", "--size",       type=int, default=1024,         help="Image size (px)")
    parser.add_argument("-o", "--output",     type=str, default="./backgrounds", help="Output directory")
    parser.add_argument("-p", "--pattern",    choices=list(PATTERNS.keys()),    help="Force a specific pattern")
    parser.add_argument("-d", "--distortion", choices=list(DISTORTIONS.keys()), help="Force a specific distortion")

    zooms = parser.add_mutually_exclusive_group()
    zooms.add_argument("--zoom",    type=float, help="Scale pattern features only")
    zooms.add_argument("--zoomall", type=float, help="Scale both pattern and distortion features")

    args = parser.parse_args()

    p_zoom = args.zoomall or args.zoom or 1.0
    d_zoom = args.zoomall or 1.0

    print(f"\nAvailable patterns:    {', '.join(PATTERNS.keys())}")
    print(f"Available distortions: {', '.join(DISTORTIONS.keys())}")
    print(f"\nGenerating {args.count} images ({args.size}x{args.size}) -> {args.output} ...\n")

    generate_batch(
        count=args.count, size=args.size, out_dir=args.output,
        p_name=args.pattern, d_name=args.distortion,
        p_zoom=p_zoom, d_zoom=d_zoom,
    )
    print("Done.\n")
