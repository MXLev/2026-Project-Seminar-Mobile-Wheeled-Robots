import math
import pytest
from practice3_odometry.odometry import Pose, integrate, integrate_history, pose_errors


def test_straight_motion_in_rotated_map_frame():
    pose = integrate(Pose(1, 2, math.pi / 2), 0.2, 0, 5)
    assert pose.x == pytest.approx(1)
    assert pose.y == pytest.approx(3)


def test_full_circle_returns_to_start():
    pose = integrate(Pose(1, 0, math.pi / 2), 0.2, 0.2, 2 * math.pi / 0.2)
    assert pose.x == pytest.approx(1)
    assert pose.y == pytest.approx(0, abs=1e-12)


def test_command_change_splits_interval():
    commands = [(0, 1.0, 0.0), (1_000_000_000, 0.0, math.pi / 2), (2_000_000_000, 1.0, 0.0)]
    pose = integrate_history(Pose(0, 0, 0), 0, 3_000_000_000, commands)
    assert pose.x == pytest.approx(1)
    assert pose.y == pytest.approx(1)
    assert pose.yaw == pytest.approx(math.pi / 2)


def test_wrap_boundary_has_small_error():
    _, error = pose_errors(Pose(0, 0, -math.pi + .01), Pose(0, 0, math.pi - .01))
    assert error == pytest.approx(.02)


def test_history_does_not_use_future_command():
    commands = [(0, 1., 0.), (2_000_000_000, 10., 0.)]
    pose = integrate_history(Pose(0, 0, 0), 0, 1_000_000_000, commands)
    assert pose.x == pytest.approx(1)


def test_missing_initial_command_is_rejected():
    with pytest.raises(ValueError):
        integrate_history(Pose(0, 0, 0), 0, 1_000_000_000, [(500_000_000, 1., 0.)])
