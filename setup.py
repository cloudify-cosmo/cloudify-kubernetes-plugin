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
import re
import sys
import pathlib
from setuptools import setup

PY2 = sys.version_info[0] == 2


def get_version():
    current_dir = pathlib.Path(__file__).parent.resolve()
    with open(os.path.join(current_dir,'cloudify_kubernetes/__version__.py'),
              'r') as outfile:
        var = outfile.read()
        return re.search(r'\d+.\d+.\d+', var).group()


install_requires = [
    'cloudify-python-importer==0.2.1',
    'cloudify-common>=4.5',
    'cloudify-types>=6.3.1',
    'deepdiff==3.3.0',
    'cloudify-utilities-plugins-sdk>=0.0.112',  # Provides kubernetes and google-auth.
]


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
