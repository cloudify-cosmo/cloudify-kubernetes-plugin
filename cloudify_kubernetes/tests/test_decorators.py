########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.


from mock import (MagicMock, patch)
import unittest

from cloudify.exceptions import RecoverableError, NonRecoverableError
from cloudify.mocks import MockCloudifyContext
from cloudify.state import current_ctx

import cloudify_kubernetes.decorators as decorators
from cloudify_kubernetes.k8s import (CloudifyKubernetesClient,
                                     KuberentesInvalidApiMethodError)


class TestDecorators(unittest.TestCase):

    def _prepare_master_node(self):
        node = MagicMock()
        node.properties = {
            'configuration': {
                'blueprint_file_name': 'kubernetes.conf'
            }
        }

        managed_master_node = MagicMock()
        managed_master_node.type = \
            decorators.RELATIONSHIP_TYPE_MANAGED_BY_MASTER
        managed_master_node.target.node = node

        _ctx = MockCloudifyContext(
            node_id="test_id",
            node_name="test_name",
            deployment_id="test_name",
            properties={
                'definition': {
                    'apiVersion': 'v1',
                    'metadata': 'c',
                    'spec': 'd',
                },
                'api_mapping': {
                    'create': {
                        'payload': 'api_payload_version',
                        'api': 'api_client_version',
                        'method': 'create'
                    },
                    'read': {
                        'api': 'api_client_version',
                        'method': 'read'
                    },
                    'delete': {
                        'api': 'api_client_version',
                        'method': 'delete'
                    }
                },
                'options': {
                    'first': 'second'
                }
            },
            runtime_properties={
                'kubernetes': {
                    'metadata': {
                        'name': "kubernetes_id"
                    }
                }
            },
            relationships=[managed_master_node],
            operation={'retry_number': 0}
        )
        _ctx._node.type = 'cloudify.nodes.Root'

        current_ctx.set(_ctx)
        return managed_master_node, _ctx

    def test_resource_task(self):
        _, _ctx = self._prepare_master_node()

        decorators.resource_task(MagicMock(), MagicMock())(MagicMock())()

        mock_isfile = MagicMock(return_value=True)
        _ctx.download_resource = MagicMock(return_value="downloaded_resource")

        with patch('os.path.isfile', mock_isfile):
            with self.assertRaises(NonRecoverableError) as error:
                decorators.resource_task(MagicMock(), MagicMock())(
                    MagicMock(
                        side_effect=KuberentesInvalidApiMethodError(
                            'error_text'
                        )
                    )
                )()

        self.assertEqual(
            str(error.exception), "error_text"
        )

    def test_retrieve_master(self):
        managed_master_node, _ctx = self._prepare_master_node()
        self.assertEqual(decorators._retrieve_master(_ctx.instance),
                         managed_master_node.target)

    def test_retrieve_property(self):
        _, _ctx = self._prepare_master_node()
        self.assertEqual(
            decorators._retrieve_property(_ctx.instance, 'configuration'),
            {'blueprint_file_name': 'kubernetes.conf'}
        )

    def test_with_kubernetes_client_RecoverableError(self):
        _, _ctx = self._prepare_master_node()

        def function(client, **kwargs):
            return client, kwargs

        with self.assertRaises(RecoverableError) as error:
            decorators.with_kubernetes_client(function)()

        self.assertEqual(
            str(error.exception),
            "Cannot initialize Kubernetes API - no suitable configuration "
            "variant found for {'blueprint_file_name': 'kubernetes.conf'} "
            "properties"
        )

    def test_with_kubernetes_client(self):
        _, _ctx = self._prepare_master_node()

        mock_isfile = MagicMock(return_value=True)

        _ctx.download_resource = MagicMock(return_value="downloaded_resource")

        def function(client, **kwargs):
            self.assertTrue(isinstance(client, CloudifyKubernetesClient))

        with patch('os.path.isfile', mock_isfile):
            with patch(
                    'cloudify_kubernetes.k8s.config.'
                    'KubernetesApiConfiguration.'
                    'get_kube_config_loader_from_file',
                    MagicMock()
            ):
                decorators.with_kubernetes_client(function)()
