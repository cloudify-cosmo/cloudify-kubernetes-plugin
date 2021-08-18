# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import inspect
from setuptools import setup

PY2 = sys.version_info[0] == 2


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()


def get_version(rel_file='plugin.yaml'):
    lines = read(rel_file)
    for line in lines.splitlines():
        if 'package_version' in line:
            split_line = line.split(':')
            line_no_space = split_line[-1].replace(' ', '')
            line_no_quotes = line_no_space.replace('\'', '')
            return line_no_quotes.strip('\n')
    raise RuntimeError('Unable to find version string.')


cloudify_types = 'cloudify-types @ ' \
                 'git+https://github.com/cloudify-cosmo/cloudify-manager.git' \
                 '@5.2.3-build#subdirectory=cloudify_types'


install_requires = [
        'cloudify-python-importer==0.2',
        'cloudify-common>=4.5',
        'kubernetes==12.0.1',
        'pyyaml>=4.2b1',
        'networkx==1.9.1',
        'pyasn1>=0.1.7',
        'pyasn1-modules',
        # 'pyasn1-modules>=0.0.5,<0.2.1',
        'oauth2client',  # used only in GCPServiceAccountAuthentication
]

if not PY2:
    install_requires.append(cloudify_types)
else:
    install_requires.append('rsa==4.5')

setup(
    name='cloudify-kubernetes-plugin',
    version=get_version(),
    author='Cloudify Platform Ltd.',
    author_email='hello@cloudify.co',
    description='Plugin provides Kubernetes management possibility',
    include_package_data=True,
    packages=['cloudify_kubernetes',
              'cloudify_kubernetes.k8s',
              'cloudify_kubernetes.tasks',
              'cloudify_kubernetes.tasks.nested_resources'],
    license='LICENSE',
    install_requires=install_requires
)
