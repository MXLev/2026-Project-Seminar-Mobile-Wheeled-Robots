"""Planar poses, exact integration of constant commands, and error metrics."""

from bisect import bisect_right
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    yaw: float


def integrate(pose, v, omega, dt):
    """Integrate a constant body-frame command without Euler discretization drift."""
    half_turn = omega * dt / 2.0
    sinc = math.sin(half_turn) / half_turn if abs(half_turn) > 1e-8 else 1 - half_turn**2 / 6
    distance = v * dt * sinc
    direction = pose.yaw + half_turn
    return Pose(
        pose.x + distance * math.cos(direction),
        pose.y + distance * math.sin(direction),
        pose.yaw + 2 * half_turn,
    )


def integrate_history(pose, start_ns, end_ns, commands):
    """Commands are (stamp_ns, v, omega); hold each until the next stamp."""
    if end_ns < start_ns:
        raise ValueError('Simulation time moved backwards')
    index = bisect_right([c[0] for c in commands], start_ns) - 1
    if index < 0:
        raise ValueError('No command available at the integration start')
    cursor = start_ns
    while cursor < end_ns:
        boundary = commands[index + 1][0] if index + 1 < len(commands) else end_ns
        boundary = min(boundary, end_ns)
        _, v, omega = commands[index]
        pose = integrate(pose, v, omega, (boundary - cursor) * 1e-9)
        cursor = boundary
        if cursor < end_ns:
            index += 1
    return pose


def pose_errors(estimate, truth):
    position = math.hypot(estimate.x - truth.x, estimate.y - truth.y)
    delta = estimate.yaw - truth.yaw
    return position, abs(math.atan2(math.sin(delta), math.cos(delta)))
