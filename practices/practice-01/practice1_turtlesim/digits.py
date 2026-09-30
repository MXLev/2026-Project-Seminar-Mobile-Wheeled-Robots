"""Seven-segment style outlines of digits for drawing with turtlesim."""

# Every digit is one continuous polyline in the coordinates of a unit cell:
# (0, 0) is the bottom-left corner of the digit and (1, 1) is its top-right corner.
# Segments may be traversed twice, so the turtle never has to lift the pen.
# Only the digits required for variant 13 are described; add a new entry to draw another digit.
DIGIT_PATHS = {
    # Right vertical bar (segments b and c).
    1: [(1.0, 0.0), (1.0, 1.0)],
    # Top bar, right side, middle bar (drawn there and back), right side, bottom bar.
    3: [(0.0, 1.0), (1.0, 1.0), (1.0, 0.5), (0.0, 0.5), (1.0, 0.5), (1.0, 0.0), (0.0, 0.0)],
}


def digit_path(digit, origin_x, origin_y, width, height):
    """
    Return the vertices of the digit polyline in turtlesim coordinates.

    The digit occupies the rectangle with the lower-left corner (origin_x, origin_y).
    """
    if digit not in DIGIT_PATHS:
        raise ValueError(
            f'Digit {digit} is not supported, available digits: {sorted(DIGIT_PATHS)}')
    return [(origin_x + u * width, origin_y + v * height) for u, v in DIGIT_PATHS[digit]]
