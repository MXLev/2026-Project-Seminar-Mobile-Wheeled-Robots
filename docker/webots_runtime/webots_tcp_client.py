"""Host launcher that keeps Webots alive until its controllers have stopped.

Installed as the common webots_ros2_driver TCP client.
The upstream client's unhandled SIGINT closes TCP immediately and kills Webots
while external controllers are still cleaning up.
"""

import os
from pathlib import Path
import signal
import socket
import sys
import time

from webots_ros2_driver.utils import controller_ip_address


def running_controllers(parent_pid):
    """Only this launch's direct children; never touch unrelated simulations."""
    children = Path(f'/proc/{parent_pid}/task/{parent_pid}/children')
    if not children.exists():
        return []
    result = []
    for pid in children.read_text().split():
        process = Path('/proc') / pid
        try:
            executable = (process / 'exe').resolve(strict=True).name
            # The standalone Python Ros2Supervisor can be blocked in step()
            # after robot controllers disconnect. Closing Webots releases it;
            # waiting for it here would create a shutdown dependency cycle.
            if executable not in ('driver', 'webots-controller'):
                continue
            if (process / 'stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z':
                result.append(int(pid))
        except (FileNotFoundError, ProcessLookupError):
            pass  # A child may finish between the two reads.
    return result


def wait_for_controllers(parent_pid, timeout=4.0):
    deadline = time.monotonic() + timeout
    while running_controllers(parent_pid):
        if time.monotonic() >= deadline:
            raise RuntimeError('Webots controllers did not finish within 4 seconds')
        time.sleep(0.05)


def receive_message(connection, stopped):
    """Handle fragmented TCP messages and allow SIGINT during a blocking recv."""
    message = b''
    while not stopped():
        try:
            # Read a token without swallowing the next one (ACK and CLOSED can
            # arrive in a single TCP packet if Webots exits immediately).
            part = connection.recv(1)
        except socket.timeout:
            continue
        if not part:
            raise RuntimeError('Local simulation server unexpectedly closed the connection')
        message += part
        if message.startswith(b'FAIL'):
            while True:
                try:
                    part = connection.recv(1024)
                except socket.timeout:
                    break
                if not part:
                    break
                message += part
            return message.decode(errors='replace')
        if message in (b'ACK', b'CLOSED'):
            return message.decode()
        if not any(token.startswith(message) for token in (b'ACK', b'CLOSED', b'FAIL')):
            raise RuntimeError(f'Unexpected simulation server response: {message!r}')
    return None


def main():
    arguments = [value for value in sys.argv[1:] if value]
    world = next((arg for arg in arguments if arg.endswith('.wbt')), None)
    if world is None:
        raise SystemExit('Webots world file is missing')
    shared = os.environ['WEBOTS_SHARED_FOLDER'].split(':', 1)[0]
    arguments[arguments.index(world)] = os.path.join(shared, world)
    command = 'webots ' + ' '.join(arguments)
    stopping = False

    def request_stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    parent_pid = os.getppid()
    connection = None
    try:
        while not stopping:
            try:
                connection = socket.create_connection((controller_ip_address(), 2000), timeout=1)
                break
            except OSError:
                print('Waiting for the local simulation server on port 2000...', flush=True)
                time.sleep(1)
        if connection is None:
            return
        connection.settimeout(0.1)
        connection.sendall(command.encode())
        response = receive_message(connection, lambda: stopping)
        if response is not None and response != 'ACK':
            raise RuntimeError(response)
        if not stopping:
            response = receive_message(connection, lambda: stopping)
            if response is not None and response != 'CLOSED':
                raise RuntimeError(response)
        if stopping:
            wait_for_controllers(parent_pid)
        print('Webots connection closed cleanly.', flush=True)
    except (OSError, RuntimeError) as error:
        print(f'Webots connection error: {error}', file=sys.stderr, flush=True)
        raise SystemExit(1) from None
    finally:
        if connection is not None:
            connection.close()


if __name__ == '__main__':
    main()
