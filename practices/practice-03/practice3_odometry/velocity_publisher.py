"""Publish one constant, simulation-stamped command at 10 Hz."""

import signal

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from geometry_msgs.msg import TwistStamped


class VelocityPublisher(Node):
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
    stopping = False

    def request_stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    previous_handlers = {signum: signal.signal(signum, request_stop)
                         for signum in (signal.SIGINT, signal.SIGTERM)}
    node = None
    try:
        # Defer context shutdown until spin_once returns: a signal must not
        # invalidate /clock subscriptions in the middle of a native ROS read.
        rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
        node = VelocityPublisher()
        while rclpy.ok() and not stopping:
            rclpy.spin_once(node, timeout_sec=0.2)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
