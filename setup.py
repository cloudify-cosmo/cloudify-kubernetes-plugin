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


from setuptools import setup

setup(
    name='cloudify-kubernetes-plugin',
    version='2.4.1',
    author='Krzysztof Bijakowski',
    author_email='krzysztof.bijakowski@gigaspaces.com',
    description='Plugin provides Kubernetes management possibility',

    packages=['cloudify_kubernetes', 'cloudify_kubernetes.k8s'],

    license='LICENSE',
    install_requires=[
        'cloudify-python-importer==0.1',
        'cloudify-plugins-common>=3.4.2',
        'kubernetes==9.0.0',
        'pyyaml>=3.12',
        'pyasn1>=0.1.7',
        'pyasn1-modules>=0.0.5,<0.2.1',
        'oauth2client',  # used only in GCPServiceAccountAuthentication
    ]
)
