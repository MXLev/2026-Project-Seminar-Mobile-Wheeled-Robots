#!/usr/bin/env python3
"""Build and install the common Webots 2025.0.0 runtime in a Docker image.

Run as root only during Docker build. Upstream files are backed up in the image.
"""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET

VERSION = '2025.0.0'
ARCHIVE_SHA256 = '52364298c9c1a8c204916de6060244b9592939b3890290a839c022fd4e7ccdf9'
URL = f'https://codeload.github.com/cyberbotics/webots_ros2/tar.gz/refs/tags/{VERSION}'


def main():
    if sys.platform != 'linux' or os.environ.get('ROS_DISTRO') != 'jazzy':
        raise SystemExit('Run inside the ROS Jazzy Linux container after sourcing /opt/ros/jazzy/setup.bash')
    for package in ('webots_ros2_driver', 'webots_ros2_control'):
        xml = Path('/opt/ros/jazzy/share') / package / 'package.xml'
        if ET.parse(xml).findtext('version') != VERSION:
            raise SystemExit(f'This patch targets {package} {VERSION}; review it before using another version')
    for command in ('cmake', 'c++', 'make', 'patch'):
        if shutil.which(command) is None:
            raise SystemExit(f'Required build tool is missing: {command}')
    if os.geteuid() != 0:
        raise SystemExit('This installer runs as root inside Docker build')
    tools = Path(__file__).resolve().parent
    runtime = Path(os.environ.get('WEBOTS_BUILD_DIR', '/tmp/robotics-webots-build'))
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / 'COLCON_IGNORE').touch()
    archive = runtime / f'webots_ros2-{VERSION}.tar.gz'
    if not archive.exists():
        print(f'Downloading official Webots ROS {VERSION} sources...', flush=True)
        temporary = archive.with_suffix('.download')
        with urllib.request.urlopen(URL, timeout=60) as response, temporary.open('wb') as output:
            shutil.copyfileobj(response, output)
        temporary.replace(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise SystemExit(f'Source archive checksum mismatch: {archive}')

    source = runtime / 'source'
    if source.exists():
        shutil.rmtree(source)  # Only generated, checksum-verified upstream sources.
    source.mkdir()
    prefix = f'webots_ros2-{VERSION}/'
    wanted = ('webots_ros2_driver/src/', 'webots_ros2_driver/include/',
              'webots_ros2_control/include/', 'webots_ros2_control/src/Ros2Control.cpp')
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            relative = member.name.removeprefix(prefix)
            if not member.isfile() or not relative.startswith(wanted):
                continue
            target = source / relative
            if not target.resolve().is_relative_to(source.resolve()):
                raise SystemExit('Unsafe archive member')
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(member) as input_file, target.open('wb') as output:
                shutil.copyfileobj(input_file, output)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(tools / 'shutdown.patch')],
                   cwd=source, check=True)
    shutil.copy2(tools / 'CMakeLists.txt', source / 'CMakeLists.txt')
    build = runtime / 'build'
    subprocess.run(['cmake', '-S', str(source), '-B', str(build), '-DCMAKE_BUILD_TYPE=Release'], check=True)
    subprocess.run(['cmake', '--build', str(build), '-j2'], check=True)
    shutil.copy2(build / 'driver', runtime / 'driver.new')
    (runtime / 'driver.new').replace(runtime / 'driver')
    from install_runtime import install
    install(runtime / 'driver', tools)
    shutil.rmtree(runtime)
    print('Common Webots runtime installed.')


if __name__ == '__main__':
    main()
