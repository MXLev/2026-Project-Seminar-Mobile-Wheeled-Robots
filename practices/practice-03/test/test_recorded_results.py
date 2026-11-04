"""Validate saved data independently of the recorder."""
import csv
import json
import math
from pathlib import Path
import pytest
from practice3_odometry.odometry import Pose, integrate, pose_errors

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('suffix,noise', [('0', 0), ('0_02', .02), ('0_1', .1)])
def test_saved_experiment(suffix, noise):
    path = ROOT / 'results' / f'noise_{suffix}.csv'
    if not path.exists():
        pytest.skip('Run experiments before validating saved data')
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    summary = json.loads(path.with_suffix('.json').read_text())
    assert len(rows) == summary['sample_count'] == 2401
    assert summary['encoder_noise'] == noise
    assert float(rows[0]['t']) == 0 and float(rows[-1]['t']) == pytest.approx(120, abs=1e-12)
    initial = Pose(*(float(rows[0][f'gt_{key}']) for key in ('x', 'y', 'yaw')))
    assert initial.x == pytest.approx(1, abs=1e-5)
    assert initial.y == pytest.approx(0, abs=1e-5)
    assert initial.yaw == pytest.approx(math.pi / 2, abs=1e-5)
    previous = None
    for row in rows:
        assert all(math.isfinite(float(value)) for value in row.values())
        stamp = int(row['stamp_ns'])
        assert stamp == int(row['gt_stamp_ns']) == int(row['odom_stamp_ns'])
        if previous is not None:
            assert stamp - previous == 50_000_000
        previous = stamp
        assert float(row['v']) == .2 and float(row['omega']) == .2
        gt = Pose(*(float(row[f'gt_{key}']) for key in ('x', 'y', 'yaw')))
        for key in ('odom', 'cmd'):
            pose = Pose(*(float(row[f'{key}_{component}']) for component in ('x', 'y', 'yaw')))
            position, yaw = pose_errors(pose, gt)
            assert float(row[f'{key}_position_error']) == pytest.approx(position)
            assert float(row[f'{key}_yaw_error']) == pytest.approx(yaw)
        expected = integrate(initial, .2, .2, float(row['t']))
        for key in ('x', 'y', 'yaw'):
            assert float(row[f'cmd_{key}']) == pytest.approx(getattr(expected, key), abs=1e-10)
    assert int(rows[-1]['stamp_ns']) - int(rows[0]['stamp_ns']) == 120_000_000_000


def test_worlds_differ_only_in_encoder_noise():
    base = (ROOT / 'worlds/my_world.wbt').read_text()
    for suffix, value in [('0_02', '0.02'), ('0_1', '0.1')]:
        other = (ROOT / f'worlds/noise_{suffix}.wbt').read_text()
        assert other == base.replace('encoderNoise 0\n', f'encoderNoise {value}\n')
