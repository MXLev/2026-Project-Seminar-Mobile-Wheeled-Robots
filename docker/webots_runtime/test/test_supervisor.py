"""Check real SIGINT delivery after Webots replaces the signal handler."""

import subprocess
import sys
import textwrap


def test_supervisor_reclaims_sigint_after_webots_initialization():
    # Isolate the real signal from pytest. Use the installed entry point but
    # replace hardware and ROS services so no simulator is required.
    program = textwrap.dedent('''
        import ast
        import os
        from pathlib import Path
        import signal
        from types import SimpleNamespace

        path = Path('/opt/ros/jazzy/lib/webots_ros2_driver/ros2_supervisor.py')
        tree = ast.parse(path.read_text())
        main = next(item for item in tree.body
                    if isinstance(item, ast.FunctionDef) and item.name == 'main')
        events = []

        class Ros2Supervisor:
            finished = False
            def __init__(self):
                # wb_robot_init replaces the Python handler in the real API.
                signal.signal(signal.SIGINT, signal.SIG_DFL)
            def destroy_node(self):
                events.append('destroy')

        def spin_once(node, timeout_sec):
            events.append('step')
            os.kill(os.getpid(), signal.SIGINT)

        rclpy = SimpleNamespace(
            init=lambda **kwargs: None,
            ok=lambda: True,
            spin_once=spin_once,
            try_shutdown=lambda: events.append('shutdown'),
        )
        SignalHandlerOptions = SimpleNamespace(NO=0)
        ExternalShutdownException = RuntimeError
        exec(compile(ast.Module(body=[main], type_ignores=[]), str(path), 'exec'))
        main()
        assert events == ['step', 'destroy', 'shutdown'], events
    ''')
    result = subprocess.run([sys.executable, '-c', program], capture_output=True,
                            text=True, timeout=5)
    assert result.returncode == 0, result.stderr
