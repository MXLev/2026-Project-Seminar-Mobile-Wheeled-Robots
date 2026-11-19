import os
from pathlib import Path
import platform

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, OpaqueFunction, RegisterEventHandler
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node
from launch_ros.event_handlers import OnStateTransition
from webots_ros2_driver.wait_for_controller_connection import WaitForControllerConnection
from webots_ros2_driver.webots_controller import WebotsController
from webots_ros2_driver.webots_launcher import WebotsLauncher


def launch_experiment(context):
    package = 'practice4_localization'
    share = Path(get_package_share_directory(package))
    scenario = LaunchConfiguration('scenario').perform(context)
    particles = LaunchConfiguration('particles').perform(context)
    clock = {'use_sim_time': True}
    tf_tolerance = 0.2
    keep_open = IfCondition(LaunchConfiguration('keep_open')).evaluate(context)

    webots = WebotsLauncher(world=str(share / 'worlds/number_13.wbt'),
                            mode=LaunchConfiguration('mode'), ros2_supervisor=False)
    supervisor = WebotsController(robot_name='ground_truth_supervisor', parameters=[
        dict(clock, robot_description=str(share / 'resource/ground_truth_supervisor.urdf'))])
    driver = WebotsController(robot_name='TurtleBot3Burger', parameters=[
        dict(clock, robot_description=str(share / 'resource/turtlebot.urdf'),
             set_robot_state_publisher=True), str(share / 'resource/ros2control.yaml')],
        remappings=[('/diffdrive_controller/cmd_vel', '/cmd_vel'),
                    ('/diffdrive_controller/odom', '/odom')])
    states = Node(package='robot_state_publisher', executable='robot_state_publisher',
                  parameters=[dict(clock, robot_description='<robot name=""><link name=""/></robot>')])
    footprint = Node(package='tf2_ros', executable='static_transform_publisher',
                     arguments=['--frame-id', 'base_link', '--child-frame-id', 'base_footprint'])
    spawner = Node(package='controller_manager', executable='spawner', output='screen',
                   arguments=['joint_state_broadcaster', 'diffdrive_controller', '--activate-as-group',
                              '--controller-manager-timeout', '50'])

    map_server = Node(package='nav2_map_server', executable='map_server', name='map_server',
                      parameters=[dict(clock, yaml_filename=str(share / 'maps/number_13.yaml'))])
    amcl = LifecycleNode(package='nav2_amcl', executable='amcl', name='amcl', namespace='',
                         output='screen', parameters=[str(share / 'config/amcl.yaml'),
                         dict(clock, min_particles=300, max_particles={'low': 1000, 'high': 10000}[particles],
                              transform_tolerance=tf_tolerance)])
    lifecycle = Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
                     name='lifecycle_manager_localization',
                     parameters=[dict(clock, autostart=True, node_names=['map_server', 'amcl'])])
    settings = {key: float(LaunchConfiguration(key).perform(context))
                for key in ('duration', 'position_threshold', 'yaw_threshold', 'hold_time')}
    experiment = Node(package=package, executable='experiment', output='screen', parameters=[
        dict(clock, **settings, scenario=scenario, particles=particles, transform_tolerance=tf_tolerance,
             keep_open=keep_open,
             output_dir=LaunchConfiguration('output_dir').perform(context))])
    # Avoid a Mesa worker crash when RViz closes in the ARM UTM container.
    rviz_env = {}
    if platform.machine() == 'aarch64' and os.environ.get('WEBOTS_SHARED_FOLDER', '').startswith('/Users/'):
        rviz_env['LIBGL_ALWAYS_SOFTWARE'] = '1'
        rviz_env['LP_NUM_THREADS'] = '0'
    rviz = Node(package='rviz2', executable='rviz2', arguments=['-d', str(share / 'rviz/config.rviz')],
                additional_env=rviz_env, parameters=[clock], condition=IfCondition(LaunchConfiguration('use_rviz')))

    def controllers_ready(event, ctx):
        if ctx.is_shutdown:
            return []
        if event.returncode:
            raise RuntimeError('Wheel controllers could not be activated')
        return [map_server, amcl, lifecycle]

    def recorder_done(event, ctx):
        if ctx.is_shutdown:
            return []
        if event.returncode:
            raise RuntimeError('Localization experiment failed; see the recorder output')
        if keep_open:
            return []
        return [EmitEvent(event=Shutdown(reason='Localization experiment complete'))]

    def webots_closed(_event, ctx):
        return [] if ctx.is_shutdown else [EmitEvent(event=Shutdown(reason='Webots closed'))]

    return [
        RegisterEventHandler(OnProcessExit(target_action=spawner, on_exit=controllers_ready)),
        RegisterEventHandler(OnStateTransition(target_lifecycle_node=amcl, goal_state='active',
                                               entities=[experiment])),
        RegisterEventHandler(OnProcessExit(target_action=experiment, on_exit=recorder_done)),
        RegisterEventHandler(OnProcessExit(target_action=webots, on_exit=webots_closed)),
        WaitForControllerConnection(target_driver=driver, nodes_to_start=[spawner]),
        states, footprint, webots, supervisor, driver, rviz,
    ]


def generate_launch_description():
    course_folder = Path.home() / 'practices_ws/src/practice-04'
    results = (course_folder if (course_folder / 'package.xml').is_file() else Path.cwd()) / 'results'
    return LaunchDescription([
        DeclareLaunchArgument('scenario', default_value='small', choices=['small', 'large', 'global']),
        DeclareLaunchArgument('particles', default_value='low', choices=['low', 'high']),
        DeclareLaunchArgument('duration', default_value='150.0', description='Simulation seconds'),
        DeclareLaunchArgument('position_threshold', default_value='0.15', description='Metres'),
        DeclareLaunchArgument('yaw_threshold', default_value='0.15', description='Radians'),
        DeclareLaunchArgument('hold_time', default_value='5.0', description='Simulation seconds'),
        DeclareLaunchArgument('use_rviz', default_value='true'),
        DeclareLaunchArgument('keep_open', default_value='false',
                              description='Keep Webots and RViz open after saving the plots'),
        DeclareLaunchArgument('mode', default_value='realtime', choices=['realtime', 'fast']),
        DeclareLaunchArgument('output_dir', default_value=str(results)),
        OpaqueFunction(function=launch_experiment),
    ])
