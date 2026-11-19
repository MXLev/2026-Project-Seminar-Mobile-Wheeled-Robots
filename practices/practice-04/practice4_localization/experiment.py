"""Initialize AMCL, drive a circle and record both TF branches on one time grid."""

import math
from time import monotonic

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, TwistStamped
from nav_msgs.msg import OccupancyGrid
from nav2_msgs.srv import SetInitialPose
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import LaserScan
from std_srvs.srv import Empty
from tf2_ros import Buffer, TransformException, TransformListener

from .results import make_sample, save_results


OFFSETS = {'small': (0.12, 0.10, 0.20), 'large': (0.55, 0.50, 1.05)}
SAMPLE_NS = 100_000_000


def planar(transform):
    p = transform.transform.translation
    q = transform.transform.rotation
    yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
    return p.x, p.y, yaw


class Experiment(Node):
    def __init__(self):
        super().__init__('localization_experiment')
        self.scenario = self.declare_parameter('scenario', 'small').value
        self.particles = self.declare_parameter('particles', 'low').value
        self.output_dir = self.declare_parameter('output_dir', 'results').value
        self.keep_open = self.declare_parameter('keep_open', False).value
        self.settings = {}
        for key, default in [('duration', 150.0), ('position_threshold', 0.15),
                             ('yaw_threshold', 0.15), ('hold_time', 5.0)]:
            value = self.declare_parameter(key, default).value
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{key} must be finite and positive')
            self.settings[key] = value
        self.duration_ns = round(self.settings['duration'] * 1e9)
        self.tf_tolerance = Duration(seconds=self.declare_parameter('transform_tolerance', 0.2).value)
        self.tf = Buffer(cache_time=Duration(seconds=30), node=self)
        self.listener = TransformListener(self.tf, self)
        self.map_ready = False
        self.scan_frame = None
        self.request = None
        self.start_ns = None
        self.next_ns = None
        self.samples = []
        self.finished = False
        self.started_waiting = monotonic()

        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(OccupancyGrid, '/map', self.on_map, latched)
        self.create_subscription(LaserScan, '/scan', self.on_scan, qos_profile_sensor_data)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.on_pose, 10)
        self.command = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        if self.scenario == 'global':
            self.initializer = self.create_client(Empty, '/reinitialize_global_localization')
        else:
            self.initializer = self.create_client(SetInitialPose, '/set_initial_pose')
        self.create_timer(0.1, self.tick)

    def on_map(self, msg):
        self.map_ready = msg.info.width > 0

    def on_scan(self, msg):
        self.scan_frame = msg.header.frame_id

    def initialize(self):
        if not (self.map_ready and self.scan_frame and self.initializer.service_is_ready()
                and self.command.get_subscription_count()
                and self.tf.can_transform('odom', self.scan_frame, Time())
                and self.tf.can_transform('map', 'base_link_gt', Time())):
            return
        if self.scenario == 'global':
            request = Empty.Request()
        else:
            dx, dy, da = OFFSETS[self.scenario]
            request = SetInitialPose.Request()
            guess = request.pose
            guess.header.frame_id = 'map'
            guess.header.stamp = self.get_clock().now().to_msg()
            # The robot starts at (0, -1.8) facing +X in number_13.wbt.
            guess.pose.pose.position.x = dx
            guess.pose.pose.position.y = -1.8 + dy
            guess.pose.pose.orientation.z = math.sin(da / 2)
            guess.pose.pose.orientation.w = math.cos(da / 2)
            guess.pose.covariance[0] = guess.pose.covariance[7] = 0.32 ** 2
            guess.pose.covariance[35] = 0.40 ** 2
        self.request = self.initializer.call_async(request)
        self.get_logger().info(f'Initializing AMCL: {self.scenario}, {self.particles}')

    def on_pose(self, msg):
        if self.request is not None and self.start_ns is None:
            self.start_ns = Time.from_msg(msg.header.stamp).nanoseconds
            self.next_ns = self.start_ns
            self.get_logger().info(f'First AMCL estimate, t0 = {self.start_ns / 1e9:.3f} s')

    def drive(self, moving):
        command = TwistStamped()
        command.header.stamp = self.get_clock().now().to_msg()
        command.header.frame_id = 'base_link'
        if moving:
            command.twist.linear.x = 0.18
            command.twist.angular.z = 0.10
        self.command.publish(command)

    def tick(self):
        if self.finished:
            self.drive(False)
            return
        if self.request is None:
            self.initialize()
            return
        if self.request.done() and self.request.exception() is not None:
            raise RuntimeError('AMCL initialization failed') from self.request.exception()
        if self.start_ns is None:
            return
        now = self.get_clock().now().nanoseconds
        end = self.start_ns + self.duration_ns
        self.drive(now < end)
        while self.next_ns <= now:
            when = Time(nanoseconds=self.next_ns)
            try:
                gt = planar(self.tf.lookup_transform('map', 'base_link_gt', when))
                # AMCL stamps map -> odom at scan time + tolerance. Keep the
                # odometry and GT at the actual measurement time.
                amcl = planar(self.tf.lookup_transform_full(
                    'map', when + self.tf_tolerance, 'base_link', when, 'odom'))
            except TransformException as error:
                # A TF stamped at the next grid point may still be in transit.
                if now - self.next_ns > 20_000_000_000:
                    raise RuntimeError(f'Missing synchronized TF at {self.next_ns / 1e9:.3f} s') from error
                return
            elapsed = (self.next_ns - self.start_ns) / 1e9
            self.samples.append(make_sample(elapsed, gt, amcl))
            if self.next_ns == end:
                name = f'{self.scenario}_{self.particles}'
                metadata = dict(self.settings, scenario=self.scenario, particles=self.particles,
                                t0_sim_s=self.start_ns / 1e9, sample_period_s=SAMPLE_NS / 1e9)
                outcome, image = save_results(self.output_dir, name, self.samples, metadata)
                self.get_logger().info(f'Эксперимент завершён. Сходимость: {outcome}. График: {image}')
                self.finished = True
                return
            self.next_ns = min(self.next_ns + SAMPLE_NS, end)


def main(args=None):
    rclpy.init(args=args)
    experiment = Experiment()
    try:
        while rclpy.ok() and (not experiment.finished or experiment.keep_open):
            rclpy.spin_once(experiment, timeout_sec=0.2)
            if experiment.start_ns is None and monotonic() - experiment.started_waiting > 90:
                raise RuntimeError('No initial AMCL pose in 90 s. Check /map, /scan, /clock and controller TF.')
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        experiment.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
