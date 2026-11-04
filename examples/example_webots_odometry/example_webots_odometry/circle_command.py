"""Publish one constant, simulation-stamped command at 10 Hz."""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped


class CircleCommand(Node):
    def __init__(self):
        super().__init__('circle_velocity_publisher')
        self.v = float(self.declare_parameter('linear_velocity', 0.2).value)
        self.omega = float(self.declare_parameter('angular_velocity', 0.2).value)
        self.publisher = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        self.timer = self.create_timer(0.1, self.publish_command)

    def publish_command(self):
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'
        msg.twist.linear.x = self.v
        msg.twist.angular.z = self.omega
        self.publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = CircleCommand()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
