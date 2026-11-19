import csv
import json
import math
from pathlib import Path
from typing import NamedTuple


class Sample(NamedTuple):
    time_s: float
    gt_x: float
    gt_y: float
    gt_yaw: float
    amcl_x: float
    amcl_y: float
    amcl_yaw: float
    position_error_m: float
    yaw_error_rad: float


def make_sample(elapsed, gt, estimate):
    dx, dy = estimate[0] - gt[0], estimate[1] - gt[1]
    da = estimate[2] - gt[2]
    return Sample(elapsed, *gt, *estimate, math.hypot(dx, dy),
                  abs(math.atan2(math.sin(da), math.cos(da))))


def convergence_time(samples, position_limit, yaw_limit, hold):
    since = None
    for row in samples:
        if row.position_error_m > position_limit or row.yaw_error_rad > yaw_limit:
            since = None
        else:
            if since is None:
                since = row.time_s
            if row.time_s - since >= hold - 1e-9:
                return since
    return None


def save_results(folder, name, samples, settings):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    directory = Path(folder).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    limit_xy, limit_yaw = settings['position_threshold'], settings['yaw_threshold']
    convergence = convergence_time(samples, limit_xy, limit_yaw, settings['hold_time'])
    with (directory / f'{name}.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(Sample._fields)
        writer.writerows(samples)

    fig, (track, pos, yaw) = plt.subplots(1, 3, figsize=(14, 4.6), constrained_layout=True)
    track.plot([r.gt_x for r in samples], [r.gt_y for r in samples], label='Webots GT', lw=2)
    track.plot([r.amcl_x for r in samples], [r.amcl_y for r in samples], '--', label='AMCL', lw=1.5)
    track.set(xlabel='X, м', ylabel='Y, м', title='Траектория', aspect='equal')
    track.legend()
    times = [r.time_s for r in samples]
    for ax, values, threshold, title, unit in [
        (pos, [r.position_error_m for r in samples], limit_xy, 'Ошибка положения', 'м'),
        (yaw, [r.yaw_error_rad for r in samples], limit_yaw, 'Ошибка курса', 'рад'),
    ]:
        ax.plot(times, values, lw=1.2)
        ax.axhline(threshold, color='tab:red', ls='--', label=f'Порог {threshold:g} {unit}')
        if convergence is not None:
            ax.axvline(convergence, color='tab:green', ls=':', lw=2,
                       label=f'Сходимость {convergence:g} с')
        ax.set(xlabel='Время от первой оценки, с', ylabel=f'Ошибка, {unit}', title=title)
        ax.legend()
    for ax in (track, pos, yaw):
        ax.grid(alpha=0.3)
    outcome = 'не подтверждена' if convergence is None else f'{convergence:g} с'
    fig.suptitle(f'{name}  |  сходимость: {outcome}')
    image = directory / f'{name}.png'
    fig.savefig(image, dpi=150)
    plt.close(fig)
    summary = dict(settings, samples=len(samples), convergence_s=convergence)
    (directory / f'{name}.json').write_text(json.dumps(summary, indent=2) + '\n')
    return outcome, image
