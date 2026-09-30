"""Helper node that prepares the turtlesim scene: kills the default turtle and spawns new ones."""

import sys

import rclpy
from rclpy.node import Node
from turtlesim.srv import Kill, Spawn


class SceneSetup(Node):
    """Call the /kill and /spawn services of turtlesim once."""

    def __init__(self):
        super().__init__('scene_setup')

        self.declare_parameter('kill_name', 'turtle1')
        self.declare_parameter('turtle_names', ['turtle_left', 'turtle_right'])
        self.declare_parameter('xs', [3.0, 5.0])
        self.declare_parameter('ys', [3.0, 9.0])
        self.declare_parameter('thetas', [0.0, 0.0])

        self.kill_client = self.create_client(Kill, '/kill')
        self.spawn_client = self.create_client(Spawn, '/spawn')

    def call(self, client, service_name, request):
        """Wait for the service, call it and return the response (None if interrupted)."""
        while not client.wait_for_service(timeout_sec=1.0):
            if not rclpy.ok():
                return None
            self.get_logger().info(f'Waiting for service {service_name}...')
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def run(self):
        """Kill the default turtle and spawn the new ones; return True on success."""
        kill_name = self.get_parameter('kill_name').value
        names = list(self.get_parameter('turtle_names').value)
        xs = list(self.get_parameter('xs').value)
        ys = list(self.get_parameter('ys').value)
        thetas = list(self.get_parameter('thetas').value)

        if self.call(self.kill_client, '/kill', Kill.Request(name=kill_name)) is None:
            return False
        self.get_logger().info(f'Killed turtle {kill_name}')

        for name, x, y, theta in zip(names, xs, ys, thetas):
            request = Spawn.Request(x=float(x), y=float(y), theta=float(theta), name=name)
            response = self.call(self.spawn_client, '/spawn', request)
            if response is None or response.name != name:
                self.get_logger().error(f'Could not spawn turtle {name}')
                return False
            self.get_logger().info(f'Spawned turtle {name} at ({x:.2f}, {y:.2f})')
        return True


def main(args=None):
    """Prepare the scene and exit with status 0 on success, 1 otherwise."""
    rclpy.init(args=args)
    node = SceneSetup()
    success = node.run()
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
