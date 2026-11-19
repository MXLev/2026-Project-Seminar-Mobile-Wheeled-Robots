from glob import glob
from setuptools import setup

name = 'practice4_localization'

setup(
    name=name,
    version='0.1.0',
    packages=[name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + name]),
        ('share/' + name, ['package.xml']),
        *[(f'share/{name}/{folder}', glob(f'{folder}/{pattern}'))
          for folder, pattern in [('launch', '*.launch.py'), ('worlds', '*.wbt'),
                                  ('protos', '*.proto'), ('maps', '*'), ('rviz', '*.rviz'),
                                  ('config', '*.yaml'), ('resource', '*.urdf'),
                                  ('resource', '*.yaml')]],
    ],
    install_requires=['setuptools'],
    maintainer='MXLev',
    maintainer_email='MXLev@users.noreply.github.com',
    description='AMCL localization experiments in the variant 13 arena',
    license='Apache-2.0',
    entry_points={'console_scripts': ['experiment = practice4_localization.experiment:main']},
)
