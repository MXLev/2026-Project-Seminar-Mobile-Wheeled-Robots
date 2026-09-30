"""Launch-файл: рисует надпись из цифр и латинских букв (до 8 символов) в turtlesim.

Запуск:
    ros2 launch practice1_turtlesim practice1_multi.launch.py text:=8642
    ros2 launch practice1_turtlesim practice1_multi.launch.py text:="HELLO"

Без аргумента рисуется 13. Старый аргумент number:=... тоже работает.
Для каждого символа создаётся своя черепаха (turtle_0, turtle_1, ...) и свой
экземпляр узла DigitDrawer (drawer_0, ...). Пробел ничего не рисует.
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    LogInfo,
    OpaqueFunction,
    RegisterEventHandler,
    TimerAction,
)
from launch.event_handlers import OnProcessStart
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from practice1_turtlesim.digits import digit_path, layout_text

PACKAGE = "practice1_turtlesim"
# Имя исполняемого файла управляющего узла из entry_points в setup.py.
# Если у тебя оно другое, поправь здесь одну строку.
DRAWER_EXECUTABLE = "digit_drawer"


def _service_call(service, srv_type, request):
    """Вызов сервиса turtlesim командой `ros2 service call`, как в примерах курса."""
    return ExecuteProcess(
        cmd=["ros2", "service", "call", service, srv_type, request],
        output="screen",
    )


def _setup(context, *args, **kwargs):
    # number - прежнее имя аргумента, оставлено для совместимости
    text = LaunchConfiguration("number").perform(context) or LaunchConfiguration(
        "text"
    ).perform(context)
    cells = layout_text(text)  # бросит ValueError, если строка не подходит

    turtlesim = Node(
        package="turtlesim", executable="turtlesim_node", name="turtlesim"
    )

    # Стандартная черепаха не нужна: рисуют только наши.
    kill_turtle = _service_call("/kill", "turtlesim/srv/Kill", "{name: turtle1}")

    spawn_calls = []
    drawers = []
    for i, cell in enumerate(cells):
        if cell.symbol == " ":
            continue  # пробел: место занято, рисовать нечего
        turtle_name = f"turtle_{i}"

        # Черепаху создаём ровно в первой точке её символа. Перо у новой черепахи
        # опущено, и иначе она нарисовала бы лишнюю линию от места появления
        # до начала символа.
        start_x, start_y = digit_path(
            cell.code, cell.origin_x, cell.origin_y, cell.width, cell.height
        )[0]
        spawn_calls.append(
            _service_call(
                "/spawn",
                "turtlesim/srv/Spawn",
                f"{{x: {start_x:.4f}, y: {start_y:.4f}, theta: 0.0, name: '{turtle_name}'}}",
            )
        )

        drawers.append(
            Node(
                package=PACKAGE,
                executable=DRAWER_EXECUTABLE,
                name=f"drawer_{i}",
                parameters=[
                    {
                        "turtle_name": turtle_name,
                        # код символа: 0-9 цифры, 10-35 буквы A-Z (целое число)
                        "digit": cell.code,
                        "origin_x": cell.origin_x,
                        "origin_y": cell.origin_y,
                        "width": cell.width,
                        "height": cell.height,
                    }
                ],
                output="screen",
            )
        )

    return [
        LogInfo(msg=f"Рисуем {text.upper()!r}: {len(drawers)} символов, по черепахе на символ"),
        turtlesim,
        RegisterEventHandler(
            OnProcessStart(
                target_action=turtlesim,
                on_start=[
                    LogInfo(msg="turtlesim запущен, убираем turtle1 и создаём черепах"),
                    kill_turtle,
                    *spawn_calls,
                ],
            )
        ),
        # Управляющие узлы стартуют чуть позже, когда черепахи уже созданы.
        TimerAction(period=1.5, actions=drawers),
    ]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "text",
                default_value="13",
                description="Что рисовать: цифры, латинские буквы и пробелы, не больше 8 символов",
            ),
            DeclareLaunchArgument(
                "number",
                default_value="",
                description="Прежнее имя аргумента text, если задан - используется вместо него",
            ),
            OpaqueFunction(function=_setup),
        ]
    )