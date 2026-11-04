"""Install version-checked runtime changes during Docker build only."""

import hashlib
import json
from pathlib import Path
import shutil
import sys


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise RuntimeError(f'Upstream source changed; expected one occurrence: {before!r}')
    return text.replace(before, after, 1)


def supervisor_source(text):
    text = replace_once(text, 'import sys\n', 'import sys\nimport signal\n')
    text = replace_once(text, 'import rclpy\n',
                        'import rclpy\nfrom rclpy.signals import SignalHandlerOptions\nfrom rclpy.executors import ExternalShutdownException\n')
    text = replace_once(text, "        super().__init__('Ros2Supervisor')",
                        "        super().__init__('Ros2Supervisor')\n        self.finished = False")
    text = replace_once(text, "        if self.__robot.step(self.__timestep) < 0:\n",
                        "        if self.__robot.step(self.__timestep) < 0:\n            self.finished = True\n")
    text = replace_once(text, '    def __spawn_urdf_robot_callback(self, request, response):\n', '''    def destroy_node(self):
        result = super().destroy_node()
        # Robot.created holds a strong reference. Release it now so Webots
        # cleanup runs while Python's SIGINT handler is still installed.
        self.__robot = None
        controller.Robot.created = None
        return result

    def __spawn_urdf_robot_callback(self, request, response):
''')
    start = text.index('def main(args=None):')
    end = text.index("\n\nif __name__ == '__main__':", start)
    return text[:start] + '''def main(args=None):
    stopping = False

    def request_stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    signal.signal(signal.SIGINT, request_stop)
    signal.siginterrupt(signal.SIGINT, False)
    node = None
    try:
        node = Ros2Supervisor()
        # wb_robot_init installs its own terminating handler. Replace it only
        # after connecting, and keep blocking controller reads restartable.
        signal.signal(signal.SIGINT, request_stop)
        signal.siginterrupt(signal.SIGINT, False)
        while rclpy.ok() and not stopping and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.1)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()
''' + text[end:]


def install(driver, tools):
    prefix = Path('/opt/ros/jazzy')
    package = prefix / 'lib/python3.12/site-packages/webots_ros2_driver'
    backup = tools / 'upstream'
    manifest = {}

    def save(path):
        relative = path.relative_to(prefix)
        target = backup / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise RuntimeError(f'Refusing to overwrite an existing upstream backup: {target}')
        shutil.copy2(path, target)
        manifest[str(relative)] = {'original_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    executable = prefix / 'lib/webots_ros2_driver/driver'
    save(executable)
    shutil.copy2(driver, executable)

    controller = package / 'webots_controller.py'
    text = controller.read_text()
    text = replace_once(text, "                'ros2',", "                os.path.join(get_package_prefix('webots_ros2_driver'), 'lib', 'webots_ros2_driver', 'driver'),")
    text = replace_once(text, "ros_args = ['--ros-args'] if ros_arguments else []",
                        "ros_args = ['--ros-args'] if ros_arguments or file_parameters else []")
    text = replace_once(text, "params_file = ['--params-file'] if file_parameters else []",
                        "params_file = [part for path in file_parameters for part in ('--params-file', path)]")
    text = replace_once(text, '                *file_parameters,\n', '')
    # The host server checks for Webots exit once per second. Leave time for
    # its CLOSED event to stop launch before respawning a completed controller.
    # Explicit caller settings remain supported (e.g. for world reloads).
    text = replace_once(text, '        super().__init__(\n',
                        "        kwargs.setdefault('respawn_delay', 2.0)\n        super().__init__(\n")
    save(controller)
    controller.write_text(text)

    launcher = package / 'webots_launcher.py'
    text = replace_once(launcher.read_text(), '        # Launch the Ros2Supervisor node\n',
                        "        kwargs.setdefault('respawn_delay', 2.0)\n        # Launch the Ros2Supervisor node\n")
    save(launcher)
    launcher.write_text(text)

    shutil.copy2(tools / 'webots_tcp_client.py', package / 'tcp_client.py')
    client = prefix / 'share/webots_ros2_driver/scripts/webots_tcp_client.py'
    save(client)
    client.write_text("#!/usr/bin/env python3\nfrom webots_ros2_driver.tcp_client import main\n\nif __name__ == '__main__':\n    main()\n")

    for supervisor in (package / 'ros2_supervisor.py', prefix / 'lib/webots_ros2_driver/ros2_supervisor.py'):
        text = supervisor_source(supervisor.read_text())
        save(supervisor)
        supervisor.write_text(text)

    for relative, entry in manifest.items():
        entry['installed_sha256'] = hashlib.sha256((prefix / relative).read_bytes()).hexdigest()
    (tools / 'manifest.json').write_text(json.dumps({
        'runtime': 'robotics-webots-common-v1', 'upstream': 'webots_ros2 2025.0.0',
        'python': sys.version.split()[0], 'files': manifest,
    }, indent=2) + '\n')
