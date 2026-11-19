"""Rasterize the arena and the seven boxes in Digit1.proto and Digit3.proto."""

import math
from pathlib import Path


RESOLUTION = 0.02
HALF_FLOOR = 3.0
HALF_MAP = HALF_FLOOR + 0.05
PIXELS = round(2 * HALF_MAP / RESOLUTION)

# (world x, world y, box width, box height in XY, rotation about Z)
BOXES = [
    (-0.6 + 0.05, 0,      0.15, 1.40, 0),
    (-0.6 - 0.13, 0.5,    0.40, 0.15, 0.7854),
    (-0.6 + 0.05, -0.625, 0.60, 0.15, 0),
    (0.6 + 0.325, 0,      0.15, 1.40, 0),
    (0.6,         0.625,  0.80, 0.15, 0),
    (0.6 + 0.1,   0,      0.60, 0.15, 0),
    (0.6,        -0.625,  0.80, 0.15, 0),
]


def occupied(x, y):
    if abs(x) >= HALF_FLOOR or abs(y) >= HALF_FLOOR:
        return True
    for cx, cy, width, height, angle in BOXES:
        dx, dy = x - cx, y - cy
        c, s = math.cos(angle), math.sin(angle)
        if abs(c * dx + s * dy) <= width / 2 and abs(-s * dx + c * dy) <= height / 2:
            return True
    return False


if __name__ == '__main__':
    directory = Path(__file__).resolve().parents[1] / 'maps'
    pixels = bytearray()
    for row in range(PIXELS):
        y = HALF_MAP - (row + 0.5) * RESOLUTION  # Image rows run from north to south.
        for col in range(PIXELS):
            x = -HALF_MAP + (col + 0.5) * RESOLUTION
            pixels.append(0 if occupied(x, y) else 254)
    (directory / 'number_13.pgm').write_bytes(f'P5\n{PIXELS} {PIXELS}\n255\n'.encode() + pixels)
    (directory / 'number_13.yaml').write_text(
        f'image: number_13.pgm\nmode: trinary\nresolution: {RESOLUTION}\n'
        f'origin: [{-HALF_MAP}, {-HALF_MAP}, 0.0]\n'
        'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.25\n'
    )
