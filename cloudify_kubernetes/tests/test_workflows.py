#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import os
from mock import patch, MagicMock

import testtools

from cloudify.mocks import MockCloudifyContext
from cloudify.state import current_ctx
from cloudify.test_utils import workflow_test

RESOURCE_CHANGES = {
    'metadata': {'resourceVersion': '0'},
    'spec': {
        'ports': [{'port': 8080}]
    }
}


def fake_workflow_context():
    fake = MockCloudifyContext()
    current_ctx.set(fake)
    setattr(fake, 'get_node_instance', MagicMock())
    setattr(fake, 'graph_mode', MagicMock())
    return fake


class TestUpdateResourceDefinition(testtools.TestCase):

    blueprint_path = os.path.join('resources', 'blueprint.yaml')

    @workflow_test(blueprint_path)
    def test_update_resource_definition(self, cfy_local):
        _ctx = fake_workflow_context()
        _parameters = {
            'node_instance_id': 'node_instance_id',
            'resource_definition_changes': RESOURCE_CHANGES
        }
        with patch('cloudify_kubernetes.k8s.config.kubernetes.config.'
                   'load_kube_config',
                   MagicMock()):
            with patch('cloudify.state.current_workflow_ctx.get_ctx',
                       return_value=_ctx):
                cfy_local.execute(
                    'update_resource_definition',
                    parameters=_parameters)
