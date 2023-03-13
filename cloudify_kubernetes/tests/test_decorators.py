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


import unittest
from mock import MagicMock, patch

from cloudify.state import current_ctx
from cloudify.mocks import MockCloudifyContext
from cloudify.exceptions import RecoverableError, NonRecoverableError

from .. import decorators
from ..k8s import (
    CloudifyKubernetesClient,
    KubernetesResourceDefinition,
    KuberentesInvalidApiMethodError)


class TestDecorators(unittest.TestCase):

    def _prepare_master_node(self, with_client_config=False,
                             with_relationship_to_master=True):
        node = MagicMock()
        node.properties = {
            'configuration': {
                'blueprint_file_name': 'kubernetes.conf',
                'api_options': {},
            }
        }

        managed_master_node = MagicMock()
        managed_master_node.type = \
            decorators.RELATIONSHIP_TYPE_MANAGED_BY_MASTER
        managed_master_node.target.node = node
        properties_dict = {
            'definition': {
                'apiVersion': 'v1',
                'metadata': {'name': 'c'},
                'spec': 'd',
                'kind': 'pod'
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
        }
        if with_client_config:
            properties_dict.update({
                'client_config': node.properties})
        _ctx = MockCloudifyContext(
            node_id="test_id",
            node_name="test_name",
            deployment_id="test_name",
            properties=properties_dict,
            runtime_properties={
                'kubernetes': {
                    'metadata': {
                        'name': "kubernetes_id"
                    }
                }
            },
            relationships=[
                managed_master_node] if with_relationship_to_master else [],
            operation={'retry_number': 0}
        )
        _ctx.node.type_hierarchy = \
            ['cloudify.nodes.Root',
             'cloudify.kubernetes.resources.BlueprintDefinedResource',
             'cloudify.kubernetes.resources.Pod']

        current_ctx.set(_ctx)
        return managed_master_node, _ctx

    def test_resource_task_retrieve_NonRecoverableError(self):
        _, _ctx = self._prepare_master_node()

        decorators.resource_task(MagicMock(), MagicMock())(MagicMock())()

        mock_isfile = MagicMock(return_value=True)
        _ctx.download_resource = MagicMock(return_value="downloaded_resource")

        defintion = KubernetesResourceDefinition(
            **_ctx.node.properties['definition'])

        with patch('os.path.isfile', mock_isfile):
            with self.assertRaises(NonRecoverableError) as error:
                decorators.resource_task(
                    retrieve_resources_definitions=MagicMock(
                        return_value=[defintion]),
                    retrieve_mapping=MagicMock()
                )(
                    MagicMock(
                        side_effect=NonRecoverableError(
                            'error_text'
                        )
                    )
                )()

        self.assertEqual(
            str(error.exception), "error_text"
        )

    def test_resource_task_retrieve_Exception(self):
        _, _ctx = self._prepare_master_node()

        decorators.resource_task(MagicMock(), MagicMock())(MagicMock())()

        mock_isfile = MagicMock(return_value=True)
        _ctx.download_resource = MagicMock(return_value="downloaded_resource")

        defintion = KubernetesResourceDefinition(
            **_ctx.node.properties['definition'])

        with patch('os.path.isfile', mock_isfile):
            with self.assertRaises(RecoverableError) as error:
                decorators.resource_task(
                    retrieve_resources_definitions=MagicMock(
                        return_value=[defintion]),
                    retrieve_mapping=MagicMock()
                )(
                    MagicMock(
                        side_effect=Exception(
                            'error_text'
                        )
                    )
                )()

        self.assertEqual(
            error.exception.causes[0]['message'], "error_text"
        )

    def test_resource_task_retrieve_resources_definitions(self):
        _, _ctx = self._prepare_master_node()

        decorators.resource_task(MagicMock(), MagicMock())(MagicMock())()

        mock_isfile = MagicMock(return_value=True)
        _ctx.download_resource = MagicMock(return_value="downloaded_resource")

        defintion = KubernetesResourceDefinition(
            **_ctx.node.properties['definition'])

        with patch('os.path.isfile', mock_isfile):
            with self.assertRaises(NonRecoverableError) as error:
                decorators.resource_task(
                    retrieve_resources_definitions=MagicMock(
                        return_value=[defintion]),
                    retrieve_mapping=MagicMock()
                )(
                    MagicMock(
                        side_effect=KuberentesInvalidApiMethodError(
                            'error_text'
                        )
                    )
                )()

        self.assertEqual(
            error.exception.causes[0]['message'], "error_text"
        )

    def test_resource_task_retrieve_resource_definition(self):
        _, _ctx = self._prepare_master_node()

        decorators.resource_task(MagicMock(), MagicMock())(MagicMock())()

        mock_isfile = MagicMock(return_value=True)
        _ctx.download_resource = MagicMock(return_value="downloaded_resource")

        with patch('os.path.isfile', mock_isfile):
            with self.assertRaises(NonRecoverableError) as error:
                decorators.resource_task(
                    retrieve_resource_definition=MagicMock(),
                    retrieve_mapping=MagicMock()
                )(
                    MagicMock(
                        side_effect=KuberentesInvalidApiMethodError(
                            'error_text'
                        )
                    )
                )()

        self.assertEqual(
            error.exception.causes[0]['message'], "error_text"
        )

    def test_retrieve_master(self):
        managed_master_node, _ctx = self._prepare_master_node()
        self.assertEqual(decorators._retrieve_master(_ctx.instance),
                         managed_master_node.target)

    def test_retrieve_property_with_relationship_to_master(self):
        _, _ctx = self._prepare_master_node()
        self.assertEqual(
            decorators._retrieve_property(_ctx, 'configuration'),
            {'api_options': {}, 'blueprint_file_name': 'kubernetes.conf'}
        )

    def test_retrieve_property_with_client_config(self):
        _, _ctx = self._prepare_master_node(with_client_config=True,
                                            with_relationship_to_master=False)
        self.assertEqual(
            decorators._retrieve_property(_ctx, 'configuration'),
            {'api_options': {}, 'blueprint_file_name': 'kubernetes.conf'}
        )

    @patch('cloudify_kubernetes.utils.AKSConnection')
    @patch('cloudify_kubernetes.decorators.'
           'setup_configuration')
    def test_with_kubernetes_client_NonRecoverableError(self, setup, aks):
        setup.return_value = True
        aks.has_service_account.return_value = None
        _, _ctx = self._prepare_master_node()

        with self.assertRaises(NonRecoverableError) as error:
            decorators.with_kubernetes_client(
                MagicMock(side_effect=NonRecoverableError(
                    'error_text')))()

        self.assertEqual(
            str(error.exception),
            "error_text"
        )

    @patch('cloudify_kubernetes.utils.AKSConnection')
    @patch('cloudify_kubernetes.decorators.'
           'setup_configuration')
    def test_with_kubernetes_client_Exception(self, setup, aks):
        setup.return_value = True
        aks.has_service_account.return_value = None
        _ctx = self._prepare_master_node()[1]

        mock_isfile = MagicMock(return_value=True)

        _ctx.download_resource = MagicMock(return_value="downloaded_resource")

        with patch('os.path.isfile', mock_isfile):
            with patch(
                    'cloudify_kubernetes_sdk.connection.decorators.'
                    'config.new_client_from_config',
                    MagicMock()
            ):
                with self.assertRaises(RecoverableError) as error:
                    decorators.with_kubernetes_client(
                        MagicMock(side_effect=Exception(
                            'error_text')))()

                self.assertEqual(
                    error.exception.causes[0]['message'],
                    "error_text"
                )

    @patch('cloudify_kubernetes.utils.AKSConnection')
    def test_with_kubernetes_client_RecoverableError(self, aks):
        aks.has_service_account.return_value = None
        _ = self._prepare_master_node()[0]

        class FakeException(Exception):
            pass

        def function(*_, **__):
            raise FakeException('Foo')

        with self.assertRaises(RecoverableError) as error:
            decorators.with_kubernetes_client(function)()
            self.assertEqual(
                error.exception.causes[0]['message'],
                "Error encountered"
            )

    @patch('cloudify_kubernetes.utils.AKSConnection')
    @patch('cloudify_kubernetes.decorators.'
           'setup_configuration')
    def test_with_kubernetes_client(self, setup, aks):
        _, _ctx = self._prepare_master_node()
        setup.return_value = True
        aks.has_service_account.return_value = None
        _ctx.download_resource = MagicMock(return_value="downloaded_resource")

        def function(client, **kwargs):
            self.assertTrue(isinstance(client, CloudifyKubernetesClient))

        decorators.with_kubernetes_client(function)()

    @patch('cloudify_kubernetes.utils.AKSConnection')
    def test_with_kubernetes_client_certificate_files(self, aks):
        _, _ctx = self._prepare_master_node(with_relationship_to_master=False,
                                            with_client_config=True)
        aks.has_service_account.return_value = None
        _ctx.node.properties['client_config'] = {
            'configuration': {
                'api_options': {
                    'host': 'foo',
                    'api_key': 'bar',
                    'verify_ssl': True,
                    'ssl_ca_cert': 'baz',
                    'cert_file': 'taco',
                    'key_file': 'bell'
                }
            }
        }

        mock_isfile = MagicMock(return_value=True)

        _ctx.download_resource = MagicMock(return_value="downloaded_resource")

        def function(client, **kwargs):
            self.assertTrue(isinstance(client, CloudifyKubernetesClient))

        with patch('os.path.isfile', mock_isfile):
            with patch(
                    'cloudify_kubernetes_sdk.connection.decorators.'
                    'config.new_client_from_config',
                    MagicMock()
            ):
                decorators.with_kubernetes_client(function)()


if __name__ == '__main__':
    unittest.main()
