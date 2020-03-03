"""
Setup to install FrundenBot as a Python package.
"""

from datetime import datetime
from os import getenv
from setuptools import find_packages, setup


def readme():
    """
    Read the full README.md file as a string.
    """
    with open('README.md') as file_read:
        return file_read.read()


def requirements():
    with open('requirements.txt') as f:
        requirements_file = f.readlines()
    return [r.strip() for r in requirements_file]


setup(
    name='frundenbot',
    version=getenv('CIRCLE_TAG', default=datetime.now().strftime('%Y.%m.%d.dev%H%M%S')),
    description='A Telegram Bot to watch your Freitagsrunde.',
    long_description=readme(),
    long_description_content_type='text/markdown',
    url='https://github.com/ekeih/FrundenBot',
    author='Max Rosin',
    author_email='frundenbot@hackrid.de',
    license='AGPLv3+',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)'
    ],
    python_requires='>=3.7',
    install_requires=requirements(),
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'frundenbot=frundenbot.main:main'
        ]
    }
)
