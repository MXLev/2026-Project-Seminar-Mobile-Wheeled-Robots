
# Only the digits required for variant 13 are described; add a new entry to draw another digit.
DIGIT_PATHS = {
    1: [(1.0, 0.0), (1.0, 1.0)],
    3: [(0.0, 1.0), (1.0, 1.0), (1.0, 0.5), (0.0, 0.5), (1.0, 0.5), (1.0, 0.0), (0.0, 0.0)],
}


def digit_path(digit, origin_x, origin_y, width, height):
    if digit not in DIGIT_PATHS:
        raise ValueError(
            f'Digit {digit} is not supported, available digits: {sorted(DIGIT_PATHS)}')
    return [(origin_x + u * width, origin_y + v * height) for u, v in DIGIT_PATHS[digit]]
