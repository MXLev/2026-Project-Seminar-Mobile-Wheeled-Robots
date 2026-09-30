"""Launch turtlesim and two digit drawers that paint the number 13 (variant 13)."""

from launch import LaunchDescription
from launch.actions import EmitEvent, LogInfo, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch_ros.actions import Node
from practice1_turtlesim.digits import digit_path

# The turtlesim window is 11 x 11 units. The number is split into the digits '1' and '3',
# every digit is drawn by its own turtle inside a cell of DIGIT_WIDTH x DIGIT_HEIGHT units
# whose lower-left corner is (origin_x, BASE_Y).
DIGIT_WIDTH = 3.0
DIGIT_HEIGHT = 6.0
BASE_Y = 2.5
DRAWERS = [
    {'node_name': 'drawer_left', 'turtle_name': 'turtle_left', 'digit': 1, 'origin_x': 0.25},
    {'node_name': 'drawer_right', 'turtle_name': 'turtle_right', 'digit': 3, 'origin_x': 4.75},
]


def generate_launch_description():
    # Every turtle is spawned exactly at the first vertex of its digit,
    # so it can start drawing immediately without drawing an extra line.
    start_points = [
        digit_path(d['digit'], d['origin_x'], BASE_Y, DIGIT_WIDTH, DIGIT_HEIGHT)[0]
        for d in DRAWERS
    ]

    turtlesim = Node(
        package='turtlesim',
        executable='turtlesim_node',
        name='turtlesim',
        output='screen',
    )

    # Kills the default turtle1 via /kill and spawns the new turtles via /spawn.
    scene_setup = Node(
        package='practice1_turtlesim',
        executable='scene_setup',
        name='scene_setup',
        output='screen',
        parameters=[{
            'kill_name': 'turtle1',
            'turtle_names': [d['turtle_name'] for d in DRAWERS],
            'xs': [x for x, _ in start_points],
            'ys': [y for _, y in start_points],
            'thetas': [0.0 for _ in DRAWERS],
        }],
    )

    # Two instances of the same program with different turtle and digit parameters.
    drawers = [
        Node(
            package='practice1_turtlesim',
            executable='digit_drawer',
            name=d['node_name'],
            output='screen',
            parameters=[{
                'turtle_name': d['turtle_name'],
                'digit': d['digit'],
                'origin_x': d['origin_x'],
                'origin_y': BASE_Y,
                'width': DIGIT_WIDTH,
                'height': DIGIT_HEIGHT,
            }],
        )
        for d in DRAWERS
    ]

    def on_scene_ready(event, context):
        if event.returncode != 0:
            return [
                LogInfo(msg='Scene setup failed, shutting down'),
                EmitEvent(event=Shutdown(reason='scene setup failed')),
            ]
        return [LogInfo(msg='Scene is ready, start drawing')] + drawers

    return LaunchDescription([
        turtlesim,
        scene_setup,
        RegisterEventHandler(
            OnProcessExit(target_action=scene_setup, on_exit=on_scene_ready)),
    ])
