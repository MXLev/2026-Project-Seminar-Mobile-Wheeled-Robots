"""Run one complete odometry experiment, including collection and plots."""

import math
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, OpaqueFunction, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from webots_ros2_driver.webots_controller import WebotsController
from webots_ros2_driver.wait_for_controller_connection import WaitForControllerConnection
from webots_ros2_driver.webots_launcher import WebotsLauncher


def start_experiment(context):
    package = Path(get_package_share_directory('practice3_odometry'))
    noise_text = LaunchConfiguration('encoder_noise').perform(context)
    noise = float(noise_text)
    suffixes = {0.0: '0', 0.02: '0_02', 0.1: '0_1'}
    if noise not in suffixes:
        raise ValueError('encoder_noise must be 0, 0.02 or 0.1')
    suffix = suffixes[noise]
    duration = float(LaunchConfiguration('duration').perform(context))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('duration must be positive and finite')
    output_dir = LaunchConfiguration('output_dir').perform(context)
    world = package / 'worlds' / ('my_world.wbt' if noise == 0 else f'noise_{suffix}.wbt')
    webots = WebotsLauncher(world=str(world), mode=LaunchConfiguration('mode'), ros2_supervisor=False)
    supervisor = WebotsController(
        robot_name='ground_truth_supervisor',
        parameters=[{'robot_description': str(package / 'resource/ground_truth_supervisor.urdf'),
                     'use_sim_time': True}],
    )
    driver = WebotsController(
        robot_name='TurtleBot3Burger',
        parameters=[{'robot_description': str(package / 'resource/turtlebot.urdf'),
                     'use_sim_time': True, 'set_robot_state_publisher': True},
                    str(package / 'resource/ros2control.yaml')],
        remappings=[('/diffdrive_controller/cmd_vel', '/cmd_vel'),
                    ('/diffdrive_controller/odom', '/odom')],
    )
    state_publisher = Node(package='robot_state_publisher', executable='robot_state_publisher',
                           parameters=[{'robot_description': '<robot name=""><link name=""/></robot>',
                                        'use_sim_time': True}])
    map_tf = Node(package='tf2_ros', executable='static_transform_publisher', arguments=[
        '--x', '1', '--y', '0', '--z', '0', '--yaw', str(math.pi / 2),
        '--frame-id', 'map', '--child-frame-id', 'odom'])
    footprint_tf = Node(package='tf2_ros', executable='static_transform_publisher', arguments=[
        '--frame-id', 'base_link', '--child-frame-id', 'base_footprint'])
    spawner = Node(package='controller_manager', executable='spawner', output='screen', arguments=[
        'joint_state_broadcaster', 'diffdrive_controller', '--activate-as-group',
        '--controller-manager-timeout', '50'])
    publisher = Node(package='practice3_odometry', executable='velocity_publisher', output='screen',
                     parameters=[{'use_sim_time': True, 'linear_velocity': 0.2, 'angular_velocity': 0.2}])
    recorder = Node(package='practice3_odometry', executable='experiment_recorder', output='screen',
                    parameters=[{'use_sim_time': True, 'duration': duration, 'encoder_noise': noise,
                                 'experiment_name': f'noise_{suffix}', 'output_dir': output_dir}])

    def controllers_ready(event, _context):
        if event.returncode != 0:
            return [EmitEvent(event=Shutdown(reason='Controller activation failed'))]
        return [publisher]

    return [
        RegisterEventHandler(OnProcessExit(target_action=spawner, on_exit=controllers_ready)),
        RegisterEventHandler(OnProcessExit(target_action=recorder,
            on_exit=[EmitEvent(event=Shutdown(reason='Experiment recorder finished'))])),
        RegisterEventHandler(OnProcessExit(target_action=webots,
            on_exit=[EmitEvent(event=Shutdown(reason='Webots closed'))])),
        WaitForControllerConnection(target_driver=driver, nodes_to_start=[spawner]),
        state_publisher, map_tf, footprint_tf, recorder, webots, supervisor, driver,
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('encoder_noise', default_value='0', description='Encoder standard deviation: 0, 0.02, 0.1 rad'),
        DeclareLaunchArgument('duration', default_value='120.0', description='Recorded duration in simulation seconds'),
        DeclareLaunchArgument('output_dir', default_value=str(Path.cwd() / 'results'), description='Directory for CSV, PNG and JSON'),
        DeclareLaunchArgument('mode', default_value='realtime', description='Webots mode: realtime or fast'),
        OpaqueFunction(function=start_experiment),
    ])
