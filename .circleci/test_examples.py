########
# Copyright (c) 2014-2019 Cloudify Platform Ltd. All rights reserved
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
import pytest

from ecosystem_tests.dorkl import (
    basic_blueprint_test,
    cleanup_on_failure, prepare_test
)

'''Temporary until all the plugins in the bundle will 
released with py2py3 wagons'''
UT_VERSION = '1.23.5'
UT_WAGON = 'https://github.com/cloudify-incubator/cloudify-utilities-plugin/' \
           'releases/download/{v}/cloudify_utilities_plugin-{v}-centos' \
           '-Core-py27.py36-none-linux_x86_64.wgn'.format(v=UT_VERSION)
UT_PLUGIN = 'https://github.com/cloudify-incubator/cloudify-utilities-' \
            'plugin/releases/download/{v}/plugin.yaml'.format(v=UT_VERSION)
GCP_VERSION = '1.6.6'
GCP_WAGON = 'https://github.com/cloudify-cosmo/cloudify-gcp-plugin/' \
            'releases/download/{v}/cloudify_gcp_plugin-{v}-centos-' \
            'Core-py27.py36-none-linux_x86_64.wgn'.format(v=GCP_VERSION)
GCP_PLUGIN = 'https://github.com/cloudify-cosmo/cloudify-gcp-plugin/releases/' \
             'download/{v}/plugin.yaml'.format(v=GCP_VERSION)
PLUGINS_TO_UPLOAD = [(UT_WAGON, UT_PLUGIN), (GCP_WAGON, GCP_PLUGIN)]
SECRETS_TO_CREATE = {
    'gcp_credentials': True
}

prepare_test(plugins=PLUGINS_TO_UPLOAD, secrets=SECRETS_TO_CREATE,
             execute_bundle_upload=False)

blueprint_list = ['examples/blueprint-examples/'
                  'kubernetes/gcp-gke/blueprint.yaml']


@pytest.fixture(scope='function', params=blueprint_list)
def blueprint_examples(request):
    dirname_param = os.path.dirname(request.param).split('/')[-1:][0]
    try:
        basic_blueprint_test(
            request.param,
            dirname_param,
            inputs='resource_prefix=kube-{0}'.format(
                os.environ['CIRCLE_BUILD_NUM']))
    except:
        cleanup_on_failure(dirname_param)
        raise


def test_blueprints(blueprint_examples):
    assert blueprint_examples is None
