"""Record three poses at identical simulation timestamps and save an experiment."""

from bisect import bisect_right
import math
from pathlib import Path
import time

import rclpy
from rclpy.clock import Clock as RosClock, ClockType
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from geometry_msgs.msg import TwistStamped
from rosgraph_msgs.msg import Clock
from tf2_ros import Buffer, TransformListener, TransformException
from tf_transformations import euler_from_quaternion

from .odometry import Pose, integrate_history
from .results import make_row, save_results


def stamp_ns(stamp):
    return stamp.sec * 1_000_000_000 + stamp.nanosec


def pose_from_transform(transform):
    p = transform.transform.translation
    q = transform.transform.rotation
    _, _, yaw = euler_from_quaternion([q.x, q.y, q.z, q.w])
    return Pose(p.x, p.y, yaw)


class ExperimentRecorder(Node):
    def __init__(self):
        super().__init__('experiment_recorder')
        self.duration = float(self.declare_parameter('duration', 120.0).value)
        self.sample_period = float(self.declare_parameter('sample_period', 0.05).value)
        self.sync_delay = float(self.declare_parameter('sync_delay', 0.2).value)
        self.noise = float(self.declare_parameter('encoder_noise', 0.0).value)
        self.output_dir = str(self.declare_parameter('output_dir', str(Path.cwd() / 'results')).value)
        self.name = str(self.declare_parameter('experiment_name', 'noise_0').value)
        if not all(math.isfinite(v) and v > 0 for v in (self.duration, self.sample_period, self.sync_delay)):
            raise ValueError('duration, sample_period and sync_delay must be finite and positive')
        if Path(self.name).name != self.name or self.name in ('', '.', '..'):
            raise ValueError('experiment_name must be a plain file name')
        self.duration_ns = round(self.duration * 1e9)
        self.period_ns = round(self.sample_period * 1e9)
        self.delay_ns = round(self.sync_delay * 1e9)
        self.sim_ns = None
        self.start_ns = None
        self.last_sample_ns = None
        self.cmd_pose = None
        self.commands = []
        self.rows = []
        self.finished = False
        self.failed = False
        self.started_wall = time.monotonic()
        self.last_report_second = -1
        self.startup_tf_error = 'No TF lookup attempted yet'

        self.tf_buffer = Buffer(cache_time=Duration(seconds=30), node=self)
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.clock_subscription = self.create_subscription(Clock, '/clock', self.clock_callback, qos_profile_sensor_data)
        self.cmd_vel_subscription = self.create_subscription(TwistStamped, '/cmd_vel', self.cmd_vel_callback, 100)
        self.sample_timer = self.create_timer(self.sample_period, self.collect)
        # Wall time is used only to diagnose a missing simulation, never for integration.
        self.watchdog = self.create_timer(1.0, self.check_startup, clock=RosClock(clock_type=ClockType.STEADY_TIME))

    def fail(self, message):
        self.get_logger().error(message)
        self.failed = self.finished = True

    def check_startup(self):
        if self.start_ns is None and time.monotonic() - self.started_wall > 90:
            self.fail(
                'No synchronized TF and commands within 90 s; no complete results saved. '
                f'clock_ns={self.sim_ns}, commands={len(self.commands)}. '
                f'Last TF error: {self.startup_tf_error}'
            )

    def clock_callback(self, msg):
        current = stamp_ns(msg.clock)
        if self.sim_ns is not None and current < self.sim_ns:
            self.fail('Simulation was reset during the experiment. Restart launch for a separate clean run.')
        self.sim_ns = current

    def cmd_vel_callback(self, msg):
        stamp = stamp_ns(msg.header.stamp)
        v, omega = msg.twist.linear.x, msg.twist.angular.z
        if not all(math.isfinite(value) for value in (v, omega)):
            self.fail('Non-finite command velocity')
            return
        if stamp <= 0:
            return  # Wait for a command stamped with simulation time.
        if self.commands and stamp < self.commands[-1][0]:
            self.fail('Command timestamps are out of order; check for a second /cmd_vel publisher')
            return
        if self.last_sample_ns is not None and stamp < self.last_sample_ns:
            if (v, omega) != self.commands[-1][1:]:
                self.fail('A changed command arrived after its pose was integrated; increase sync_delay')
                return
        command = (stamp, v, omega)
        if self.commands and stamp == self.commands[-1][0]:
            self.commands[-1] = command
        else:
            self.commands.append(command)

    def read_transforms(self, when_ns):
        when = Time(nanoseconds=when_ns, clock_type=ClockType.ROS_TIME)
        # tf2 interpolates both branches at the exact same requested timestamp.
        gt = self.tf_buffer.lookup_transform('map', 'base_link_gt', when)
        odom = self.tf_buffer.lookup_transform('map', 'base_link', when)
        if stamp_ns(gt.header.stamp) != when_ns or stamp_ns(odom.header.stamp) != when_ns:
            raise RuntimeError('TF returned mismatched timestamps')
        return pose_from_transform(gt), pose_from_transform(odom)

    def read_initial_transforms(self, available_ns):
        first_command_ns = self.commands[0][0]
        try:
            gt, odom = self.read_transforms(first_command_ns)
            return first_command_ns, gt, odom
        except TransformException:
            # A late TF publisher/listener may never have the first command's
            # timestamp (especially in Fast mode). Find a newer common time.
            latest_gt = self.tf_buffer.lookup_transform('map', 'base_link_gt', Time())
            latest_odom = self.tf_buffer.lookup_transform('map', 'base_link', Time())
            initial_ns = min(available_ns, stamp_ns(latest_gt.header.stamp),
                             stamp_ns(latest_odom.header.stamp))
            if initial_ns < first_command_ns:
                raise TransformException('Both TF branches must reach the first command timestamp')
            # Latest poses can have different stamps. Always re-read BOTH at
            # the chosen time; never compare their separate latest values.
            gt, odom = self.read_transforms(initial_ns)
            return initial_ns, gt, odom

    def collect(self):
        if self.finished or self.sim_ns is None or not self.commands:
            return
        available_ns = self.sim_ns - self.delay_ns
        if self.start_ns is None:
            if available_ns < self.commands[0][0] or available_ns <= 0:
                return
            try:
                initial_ns, gt, odom = self.read_initial_transforms(available_ns)
            except TransformException as error:
                self.startup_tf_error = str(error)
                return
            self.start_ns = self.last_sample_ns = initial_ns
            self.cmd_pose = gt  # The only use of GT in command integration.
            self.append_sample(initial_ns, gt, odom)
            self.get_logger().info(f'Started: noise={self.noise}, duration={self.duration}s, t0={initial_ns * 1e-9:.3f}s')
            if initial_ns > self.commands[0][0]:
                self.get_logger().info('Initial TF was unavailable; recording starts at a newer synchronized timestamp.')

        end_ns = self.start_ns + self.duration_ns
        next_ns = min(self.last_sample_ns + self.period_ns, end_ns)
        while next_ns <= available_ns and not self.finished:
            try:
                gt, odom = self.read_transforms(next_ns)
            except TransformException:
                if self.sim_ns - next_ns > 5_000_000_000:
                    self.fail('TF is missing for more than 5 simulation seconds; no complete results saved')
                return
            self.cmd_pose = integrate_history(self.cmd_pose, self.last_sample_ns, next_ns, self.commands)
            self.last_sample_ns = next_ns
            self.append_sample(next_ns, gt, odom)
            if next_ns == end_ns:
                self.finish()
                return
            next_ns = min(next_ns + self.period_ns, end_ns)

    def append_sample(self, stamp, gt, odom):
        index = bisect_right([c[0] for c in self.commands], stamp) - 1
        _, v, omega = self.commands[index]
        row = make_row(stamp, self.start_ns, gt, odom, self.cmd_pose, v, omega)
        self.rows.append(row)
        second = int(row['t'])
        if second // 10 != self.last_report_second // 10:
            self.get_logger().info(f"t={row['t']:.1f}s | wheel error={row['odom_position_error']:.3f}m | command error={row['cmd_position_error']:.3f}m")
            self.last_report_second = second

    def finish(self):
        figure = save_results(self.rows, self.commands, self.output_dir, self.name, {
            'duration': self.duration, 'sample_period': self.sample_period,
            'sync_delay': self.sync_delay, 'encoder_noise': self.noise,
            'integration': 'exact piecewise-constant unicycle',
            'alignment': 'tf2 lookup at identical simulation timestamps',
        })
        self.get_logger().info(f'EXPERIMENT COMPLETE: {len(self.rows)} samples; saved {figure}')
        self.finished = True


def main(args=None):
    rclpy.init(args=args)
    node = None
    exit_code = 0
    try:
        node = ExperimentRecorder()
        while rclpy.ok() and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.2)
        exit_code = 1 if node.failed else 0
    except (KeyboardInterrupt, ExternalShutdownException):
        # User/launch cancellation is normal; incomplete data is not presented
        # as a successful experiment and does not replace existing results.
        exit_code = 1 if node is not None and node.failed else 0
    finally:
        if node is not None:
            if not node.finished:
                print('Experiment stopped early; no complete results saved.', flush=True)
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == '__main__':
    main()
