"""Save aligned measurements and a three-panel figure without a desktop backend."""

import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from .odometry import pose_errors

FIELDS = ['t', 'stamp_ns', 'gt_stamp_ns', 'odom_stamp_ns',
          'gt_x', 'gt_y', 'gt_yaw', 'odom_x', 'odom_y', 'odom_yaw',
          'cmd_x', 'cmd_y', 'cmd_yaw', 'v', 'omega',
          'odom_position_error', 'cmd_position_error', 'odom_yaw_error', 'cmd_yaw_error']


def make_row(stamp_ns, start_ns, gt, odom, cmd, v, omega):
    odom_error = pose_errors(odom, gt)
    cmd_error = pose_errors(cmd, gt)
    values = [(stamp_ns - start_ns) * 1e-9, stamp_ns, stamp_ns, stamp_ns,
              gt.x, gt.y, gt.yaw, odom.x, odom.y, odom.yaw,
              cmd.x, cmd.y, cmd.yaw, v, omega,
              odom_error[0], cmd_error[0], odom_error[1], cmd_error[1]]
    return dict(zip(FIELDS, values))


def save_results(rows, commands, output_dir, name, metadata):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / f'{name}.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with (destination / f'{name}_commands.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['stamp_ns', 'v', 'omega'])
        writer.writerows(commands)

    data = {field: np.array([row[field] for row in rows]) for field in FIELDS}
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), constrained_layout=True)
    labels = [('gt', 'Ground truth', '#222222'), ('odom', 'Wheel odometry', '#0072B2'),
              ('cmd', 'Command odometry', '#D55E00')]
    for key, label, color in labels:
        axes[0].plot(data[f'{key}_x'], data[f'{key}_y'], label=label, color=color, linewidth=1.5)
    axes[0].scatter(data['gt_x'][0], data['gt_y'][0], marker='x', color='green', label='Start', zorder=5)
    axes[0].set(xlabel='x [m]', ylabel='y [m]', title='Trajectories in map')
    axes[0].set_aspect('equal', adjustable='box')
    for key, label, color in labels[1:]:
        axes[1].plot(data['t'], data[f'{key}_position_error'], label=label, color=color)
        axes[2].plot(data['t'], data[f'{key}_yaw_error'], label=label, color=color)
    axes[1].set(xlabel='Simulation time since start [s]', ylabel='Position error [m]', title='Absolute position error')
    axes[2].set(xlabel='Simulation time since start [s]', ylabel='Yaw error [rad]', title='Absolute wrapped yaw error')
    for axis in axes:
        axis.grid(True, alpha=0.3)
        axis.legend(fontsize=9)
    fig.suptitle(f"Encoder noise: {metadata['encoder_noise']} rad | duration: {metadata['duration']} s")
    fig.savefig(destination / f'{name}.png', dpi=160)
    plt.close(fig)
    summary = dict(metadata, saved_at_utc=datetime.now(timezone.utc).isoformat(),
                   sample_count=len(rows), start_stamp_ns=rows[0]['stamp_ns'],
                   end_stamp_ns=rows[-1]['stamp_ns'], frame='map',
                   initial_gt={key: rows[0][f'gt_{key}'] for key in ('x', 'y', 'yaw')},
                   commands_used=sorted({(row['v'], row['omega']) for row in rows}))
    summary['errors'] = {}
    for key in ('odom_position_error', 'cmd_position_error', 'odom_yaw_error', 'cmd_yaw_error'):
        values = data[key]
        summary['errors'][key] = {'rmse': float(np.sqrt(np.mean(values**2))),
                                  'max': float(np.max(values)), 'final': float(values[-1])}
    (destination / f'{name}.json').write_text(json.dumps(summary, indent=2) + '\n')
    return destination / f'{name}.png'
