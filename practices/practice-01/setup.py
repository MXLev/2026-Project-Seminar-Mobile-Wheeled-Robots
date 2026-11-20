from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'practice1_turtlesim'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='LeoSkuratov',
    maintainer_email='lsskuratov@edu.hse.ru',
    description='Draws the number 13 (variant 13) with two turtles in turtlesim.',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'digit_drawer = practice1_turtlesim.digit_drawer:main',
            'scene_setup = practice1_turtlesim.scene_setup:main',
        ],
    },
)
