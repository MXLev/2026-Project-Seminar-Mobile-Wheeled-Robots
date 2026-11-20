import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    """Start the number 13 world and publish a constant velocity to drive around the digits."""
    package_dir = get_package_share_directory('practice2_webots')

    linear_speed = LaunchConfiguration('linear_speed')
    angular_speed = LaunchConfiguration('angular_speed')

    number_world = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(package_dir, 'launch', 'number_world.launch.py')))

    # The same command as in README: constant v and w give a circle of radius v / w
    cmd_vel_publisher = ExecuteProcess(
        cmd=[
            'ros2', 'topic', 'pub', '-r', '10', '/cmd_vel', 'geometry_msgs/msg/TwistStamped',
            ["{header: {stamp: {sec: 0, nanosec: 0}, frame_id: 'base_link'}, "
             'twist: {linear: {x: ', linear_speed, ', y: 0.0, z: 0.0}, '
             'angular: {x: 0.0, y: 0.0, z: ', angular_speed, '}}}'],
        ],
        output='log',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'linear_speed', default_value='0.18', description='Linear speed, m/s'),
        DeclareLaunchArgument(
            'angular_speed', default_value='0.1', description='Angular speed, rad/s'),
        number_world,
        cmd_vel_publisher,
    ])
