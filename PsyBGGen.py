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

# --- Patterns ---

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
    
    x, y = np.meshgrid(np.arange(size) - size/2, np.arange(size) - size/2)
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

PATTERNS = {'chessboard': chessboard, 'stripes': stripes, 'circles': concentric_circles}

# --- Distortions ---

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

    # Upsample noise to full image size
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

DISTORTIONS = {'ripple': ripple, 'grid': grid_displacement, 'warp': warp, 'swirl': swirl}

# --- Main Pipeline ---

def generate_batch(count, size, out_dir, p_name=None, d_name=None, p_zoom=1.0, d_zoom=1.0):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, count + 1):
        seed = random.randint(0, 2**31)
        random.seed(seed)
        np.random.seed(seed)

        pattern_func = PATTERNS.get(p_name) or random.choice(list(PATTERNS.values()))
        distort_func = DISTORTIONS.get(d_name) or random.choice(list(DISTORTIONS.values()))

        arr = pattern_func(size, zoom=p_zoom)
        arr = distort_func(arr, zoom=d_zoom)

        filename = out_dir / f"bg_{i:03d}_seed{seed}.png"
        Image.fromarray(arr, mode='L').save(filename)
        print(f"Saved {i}/{count} -> {filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate randomized background patterns.")
    parser.add_argument("-n", "--count", type=int, default=10, help="Number of images")
    parser.add_argument("-s", "--size", type=int, default=1024, help="Image size (px)")
    parser.add_argument("-o", "--output", type=str, default="./backgrounds", help="Output dir")
    parser.add_argument("-p", "--pattern", choices=list(PATTERNS.keys()), help="Force a pattern")
    parser.add_argument("-d", "--distortion", choices=list(DISTORTIONS.keys()), help="Force a distortion")
    
    zooms = parser.add_mutually_exclusive_group()
    zooms.add_argument("--zoom", type=float, help="Scale pattern features only")
    zooms.add_argument("--zoomall", type=float, help="Scale both pattern and distortion features")

    args = parser.parse_args()

    p_zoom = args.zoomall or args.zoom or 1.0
    d_zoom = args.zoomall or 1.0

    print(f"\nGenerating {args.count} images ({args.size}x{args.size}) to {args.output} ...")
    generate_batch(
        count=args.count, size=args.size, out_dir=args.output,
        p_name=args.pattern, d_name=args.distortion, 
        p_zoom=p_zoom, d_zoom=d_zoom
    )
    print("Done.\n")
