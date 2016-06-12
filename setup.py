#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of django-confirm (https://github.com/mathiasertl/django-confirm).
#
# django-confirm is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# django-confirm is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
# the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with django-confirm.  If
# not, see <http://www.gnu.org/licenses/>.

import os
import sys

from distutils.cmd import Command
from setuptools import setup


long_description = ""
_rootdir = os.path.dirname(os.path.realpath(__file__))


def find_package_data(dir):
    data = []
    package_root = os.path.join('confirm', 'django_confirm')
    for root, dirs, files in os.walk(os.path.join(package_root, dir)):
        for file in files:
            data.append(os.path.join(root, file).lstrip(package_root))
    return data

package_data = []
#package_data = find_package_data('static') + \
#               find_package_data('templates')

setup(
    name='django-confirm',
    version='0.1.0',
    description='Send confirmation keys.',
    long_description=long_description,
    author='Mathias Ertl',
    author_email='mati@er.tl',
    url='https://github.com/mathiasertl/django-confirm',
    packages=[
        'django_confirm',
        'django_confirm.migrations',
    ],
    package_dir={'': 'confirm'},
    package_data={'': package_data},
    zip_safe=False,  # because of the static files
    install_requires=[
        'Django>=1.8',
        'django-jsonfield==1.0.0',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)
