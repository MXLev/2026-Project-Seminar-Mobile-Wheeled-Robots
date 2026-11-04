"""Regression checks for normal termination versus a real server failure."""

import socket

import pytest

from webots_ros2_driver.tcp_client import receive_message, wait_for_controllers


def test_coalesced_messages_remain_separate():
    client, server = socket.socketpair()
    with client, server:
        client.settimeout(0.1)
        server.sendall(b'ACKCLOSED')
        assert receive_message(client, lambda: False) == 'ACK'
        assert receive_message(client, lambda: False) == 'CLOSED'


def test_unexpected_disconnect_is_an_error():
    client, server = socket.socketpair()
    with client:
        server.close()
        with pytest.raises(RuntimeError, match='unexpectedly closed'):
            receive_message(client, lambda: False)


def test_intentional_cancellation_does_not_read():
    client, server = socket.socketpair()
    with client, server:
        assert receive_message(client, lambda: True) is None


def test_server_error_keeps_diagnostic():
    client, server = socket.socketpair()
    with client, server:
        client.settimeout(0.01)
        server.sendall(b'FAIL: world file is missing')
        assert receive_message(client, lambda: False) == 'FAIL: world file is missing'


def test_unknown_response_is_an_error():
    client, server = socket.socketpair()
    with client, server:
        server.sendall(b'wrong')
        with pytest.raises(RuntimeError, match='Unexpected'):
            receive_message(client, lambda: False)


def test_stuck_controller_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr('webots_ros2_driver.tcp_client.running_controllers', lambda _: [123])
    with pytest.raises(RuntimeError, match='did not finish'):
        wait_for_controllers(1, timeout=0)
