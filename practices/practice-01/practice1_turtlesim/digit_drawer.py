"""Universal node that draws one digit with one turtlesim turtle."""

import math

from geometry_msgs.msg import Twist
from practice1_turtlesim.digits import digit_path
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from turtlesim.msg import Pose


def normalize_angle(angle):
    """Wrap an angle to the range [-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


class DigitDrawer(Node):
    """
    Drive one turtle along the segments of a digit using the pose feedback.

    The digit is a list of actions: turn to an absolute angle, then drive a segment
    of a given length, and so on. The end of every action is detected from /<turtle>/pose.
    """

    # Proportional slow-down near the goal and the lowest speeds that are still used,
    # so the turtle does not overshoot the target angle or the end of a segment.
    ANGULAR_GAIN = 8.0
    MIN_ANGULAR_SPEED = 0.1
    LINEAR_GAIN = 6.0
    MIN_LINEAR_SPEED = 0.1

    def __init__(self):
        super().__init__('digit_drawer')

        self.declare_parameter('turtle_name', 'turtle1')
        self.declare_parameter('digit', 1)
        self.declare_parameter('origin_x', 1.0)
        self.declare_parameter('origin_y', 3.0)
        self.declare_parameter('width', 3.0)
        self.declare_parameter('height', 6.0)
        self.declare_parameter('linear_speed', 2.0)
        self.declare_parameter('angular_speed', 2.5)
        self.declare_parameter('angle_tolerance', 0.005)
        self.declare_parameter('distance_tolerance', 0.01)
        self.declare_parameter('rate_hz', 50.0)

        self.turtle_name = self.get_parameter('turtle_name').value
        self.linear_speed = float(self.get_parameter('linear_speed').value)
        self.angular_speed = float(self.get_parameter('angular_speed').value)
        self.angle_tolerance = float(self.get_parameter('angle_tolerance').value)
        self.distance_tolerance = float(self.get_parameter('distance_tolerance').value)
        rate_hz = float(self.get_parameter('rate_hz').value)

        points = digit_path(
            int(self.get_parameter('digit').value),
            float(self.get_parameter('origin_x').value),
            float(self.get_parameter('origin_y').value),
            float(self.get_parameter('width').value),
            float(self.get_parameter('height').value))
        self.actions = self.build_actions(points)
        self.action_index = 0
        self.segment_start = None
        self.pose = None

        self.cmd_pub = self.create_publisher(Twist, f'/{self.turtle_name}/cmd_vel', 10)
        self.pose_sub = self.create_subscription(
            Pose, f'/{self.turtle_name}/pose', self.on_pose, 10)
        self.timer = self.create_timer(1.0 / rate_hz, self.on_timer)

        self.get_logger().info(
            f'Drawing digit {self.get_parameter("digit").value} with {self.turtle_name}: '
            f'{len(self.actions)} actions')

    @staticmethod
    def build_actions(points):
        """Convert polyline vertices to a list of ('turn', angle) and ('move', length)."""
        actions = []
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            actions.append(('turn', math.atan2(y1 - y0, x1 - x0)))
            actions.append(('move', math.hypot(x1 - x0, y1 - y0)))
        return actions

    def on_pose(self, msg):
        """Remember the latest pose of the turtle."""
        self.pose = msg

    def on_timer(self):
        """Publish the command of the current action or zero velocity."""
        cmd = Twist()
        if self.pose is not None and self.action_index < len(self.actions):
            kind, value = self.actions[self.action_index]
            if kind == 'turn':
                done = self.update_turn(cmd, value)
            else:
                done = self.update_move(cmd, value)
            if done:
                cmd = Twist()
                self.segment_start = None
                self.action_index += 1
                if self.action_index == len(self.actions):
                    self.get_logger().info('Drawing finished, publishing zero velocity')
        self.cmd_pub.publish(cmd)

    def update_turn(self, cmd, target_angle):
        """Rotate in place to the absolute angle; return True when the angle is reached."""
        error = normalize_angle(target_angle - self.pose.theta)
        if abs(error) < self.angle_tolerance:
            return True
        speed = min(self.angular_speed,
                    max(self.MIN_ANGULAR_SPEED, self.ANGULAR_GAIN * abs(error)))
        cmd.angular.z = math.copysign(speed, error)
        return False

    def update_move(self, cmd, length):
        """Drive straight for the given length; return True when it has been covered."""
        if self.segment_start is None:
            self.segment_start = (self.pose.x, self.pose.y)
        start_x, start_y = self.segment_start
        remaining = length - math.hypot(self.pose.x - start_x, self.pose.y - start_y)
        if remaining <= self.distance_tolerance:
            return True
        cmd.linear.x = min(self.linear_speed,
                           max(self.MIN_LINEAR_SPEED, self.LINEAR_GAIN * remaining))
        return False


def main(args=None):
    """Run the digit drawer node until it is shut down."""
    rclpy.init(args=args)
    node = DigitDrawer()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
