import os
from os import path

from setuptools import find_packages, setup

VERSION = "0.0.1"

INSTALL_REQUIRES = [
    "Django==4.2.7",
    "bleach==6.1.0",
    "bleach-whitelist>=0.0.11",
    "cryptography>=41.0.5",
    "django-after-response>=0.2.2",
    "django-bootstrap4>=23.2",
    "djangorestframework>=3.14.0",
    "emoji-data-python==1.5.0",
    "jsonfield>=3.1.0",
    "markdown2>=2.4.10",
    "python-slugify>=8.0.1",
    "slack_bolt>=1.18.0",
    "apscheduler==3.10.4"
]

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))


setup(
    name="django-incident-response",
    version=VERSION,
    packages=find_packages(exclude="demo"),
    install_requires=INSTALL_REQUIRES,
)
