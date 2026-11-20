import os

from ament_index_python.packages import get_package_share_directory
import launch
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from webots_ros2_driver.wait_for_controller_connection import WaitForControllerConnection
from webots_ros2_driver.webots_controller import WebotsController
from webots_ros2_driver.webots_launcher import WebotsLauncher


def generate_launch_description():
    """Start Webots with the number 13 world, the TurtleBot3 driver and its controllers."""
    turtlebot_package_dir = get_package_share_directory('webots_ros2_turtlebot')
    package_dir = get_package_share_directory('practice2_webots')

    world = LaunchConfiguration('world')
    mode = LaunchConfiguration('mode')
    use_sim_time = LaunchConfiguration('use_sim_time', default=True)

    webots = WebotsLauncher(
        world=PathJoinSubstitution([package_dir, 'worlds', world]),
        mode=mode,
        ros2_supervisor=True,
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': '<robot name=""><link name=""/></robot>',
        }],
    )

    footprint_publisher = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        output='screen',
        arguments=['0', '0', '0', '0', '0', '0', 'base_link', 'base_footprint'],
    )

    # ros2_control spawners for the wheels
    controller_manager_timeout = ['--controller-manager-timeout', '50']
    diffdrive_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        output='screen',
        arguments=['diffdrive_controller'] + controller_manager_timeout,
    )
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        output='screen',
        arguments=['joint_state_broadcaster'] + controller_manager_timeout,
    )

    robot_description_path = os.path.join(
        turtlebot_package_dir, 'resource', 'turtlebot_webots.urdf')
    ros2_control_params = os.path.join(turtlebot_package_dir, 'resource', 'ros2control.yml')
    # Starting from Jazzy the diff drive controller takes TwistStamped on cmd_vel
    use_twist_stamped = os.environ.get('ROS_DISTRO') in ['rolling', 'jazzy', 'kilted']
    if use_twist_stamped:
        mappings = [('/diffdrive_controller/cmd_vel', '/cmd_vel'),
                    ('/diffdrive_controller/odom', '/odom')]
    else:
        mappings = [('/diffdrive_controller/cmd_vel_unstamped', '/cmd_vel'),
                    ('/diffdrive_controller/odom', '/odom')]
    turtlebot_driver = WebotsController(
        robot_name='TurtleBot3Burger',
        parameters=[
            {'robot_description': robot_description_path,
             'use_sim_time': use_sim_time,
             'set_robot_state_publisher': True},
            ros2_control_params,
        ],
        remappings=mappings,
        respawn=True,
    )

    # Start the controllers only when the robot driver is connected to the simulation
    waiting_nodes = WaitForControllerConnection(
        target_driver=turtlebot_driver,
        nodes_to_start=[diffdrive_controller_spawner, joint_state_broadcaster_spawner],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'world',
            default_value='number_13.wbt',
            description='World file from the `worlds` directory of the package',
        ),
        DeclareLaunchArgument(
            'mode',
            default_value='realtime',
            description='Webots startup mode',
        ),
        webots,
        webots._supervisor,
        robot_state_publisher,
        footprint_publisher,
        turtlebot_driver,
        waiting_nodes,
        # Shut down all nodes when Webots is closed
        launch.actions.RegisterEventHandler(
            event_handler=launch.event_handlers.OnProcessExit(
                target_action=webots,
                on_exit=[launch.actions.EmitEvent(event=launch.events.Shutdown())],
            )
        ),
    ])
