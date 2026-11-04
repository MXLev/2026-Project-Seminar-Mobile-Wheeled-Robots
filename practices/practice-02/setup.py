from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'practice2_webots'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
        (os.path.join('share', package_name, 'worlds'),
            glob(os.path.join('worlds', '*.wbt'))),
        (os.path.join('share', package_name, 'protos'),
            glob(os.path.join('protos', '*.proto'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='MXLev',
    maintainer_email='skuratov.lev@gmail.com',
    description='Practice 2: TurtleBot3 in Webots around the number 13',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
        ],
    },
)
