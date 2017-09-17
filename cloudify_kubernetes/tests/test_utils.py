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

import unittest
from mock import (MagicMock, mock_open, patch)

from cloudify.mocks import MockCloudifyContext
from cloudify.state import current_ctx

from cloudify_kubernetes import utils
from cloudify_kubernetes.k8s.client import KubernetesResourceDefinition
from cloudify_kubernetes.k8s.exceptions import (
    KuberentesInvalidDefinitionError,
    KuberentesMappingNotFoundError
)
from cloudify_kubernetes.k8s.mapping import (
    KubernetesSingleOperationApiMapping,
    KubernetesApiMapping
)


class TestUtils(unittest.TestCase):

    def _assert_mapping(self, mapping):
        self.assertTrue(
            isinstance(
                mapping,
                KubernetesApiMapping
            )
        )

        self.assertTrue(
            isinstance(
                mapping.read,
                KubernetesSingleOperationApiMapping
            )
        )

        self.assertEqual(mapping.read.api, 'CoreV1Api')
        self.assertEqual(mapping.read.method, 'read_namespaced_pod')
        self.assertEqual(mapping.read.payload, None)

        self.assertTrue(
            isinstance(
                mapping.create,
                KubernetesSingleOperationApiMapping
            )
        )

        self.assertEqual(mapping.create.api, 'CoreV1Api')
        self.assertEqual(mapping.create.method, 'create_namespaced_pod')
        self.assertEqual(mapping.create.payload, 'V1Pod')

        self.assertTrue(
            isinstance(
                mapping.delete,
                KubernetesSingleOperationApiMapping
            )
        )

        self.assertEqual(mapping.delete.api, 'CoreV1Api')
        self.assertEqual(mapping.delete.method, 'delete_namespaced_pod')
        self.assertEqual(mapping.delete.payload, 'V1DeleteOptions')

    def _prepare_context(self,
                         with_api_mapping=False,
                         with_definition=True,
                         kind=None):

        properties = {
            'options': {
                'first': 'second'
            }
        }

        if with_definition:
            properties['definition'] = {
                'apiVersion': 'v1',
                'metadata': 'c',
                'spec': 'd'
            }

        if kind:
            properties['definition']['kind'] = kind

        if with_api_mapping:
            properties['api_mapping'] = self._prepare_mapping()

        _ctx = MockCloudifyContext(
            node_id="test_id",
            node_name="test_name",
            deployment_id="test_name",
            properties=properties,
            runtime_properties={
                'kubernetes': {
                    'metadata': {
                        'name': "kubernetes_id"
                    }
                }
            },
            relationships=[],
            operation={'retry_number': 0}
        )

        _ctx._node.type = 'cloudify.kubernetes.resources.Pod'

        current_ctx.set(_ctx)
        return _ctx

    def _prepare_mapping(self):
        return {
            'create': {
                'api': 'CoreV1Api',
                'method': 'create_namespaced_pod',
                'payload': 'V1Pod'
            },
            'read': {
                'api': 'CoreV1Api',
                'method': 'read_namespaced_pod',
            },
            'delete': {
                'api': 'CoreV1Api',
                'method': 'delete_namespaced_pod',
                'payload': 'V1DeleteOptions'
            },
        }

    def test_yaml_from_file(self):
        yaml_data = 'test: \n  a: 1 \n  b: 2'

        _ctx = MockCloudifyContext()
        _ctx.download_resource_and_render = \
            lambda resource_path, target_path, template_variables: \
            'local_path' if resource_path == 'path' else None

        current_ctx.set(_ctx)

        with patch(
                'cloudify_kubernetes.utils.open',
                mock_open(read_data=yaml_data)
        ) as file_mock:
            result = utils._yaml_from_file('path')

            self.assertEquals(result, {'test': {'a': 1, 'b': 2}})
            file_mock.assert_called_once_with('local_path')

    def test_mapping_by_data_kwargs(self):
        self._prepare_context(with_api_mapping=False)
        mapping = self._prepare_mapping()
        self._assert_mapping(
            utils.mapping_by_data(None, api_mapping=mapping)
        )

    def test_mapping_by_data_properties(self):
        self._prepare_context(with_api_mapping=True)
        self._assert_mapping(
            utils.mapping_by_data(None)
        )

    def test_mapping_by_data_error(self):
        self._prepare_context(with_api_mapping=False)

        with self.assertRaises(KuberentesMappingNotFoundError):
            utils.mapping_by_data(None)

    def test_mapping_by_kind(self):
        self._prepare_context(with_api_mapping=False)

        resource_definition = MagicMock()
        resource_definition.kind = 'Pod'

        self._assert_mapping(
            utils.mapping_by_kind(resource_definition)
        )

    def test_mapping_by_kind_error(self):
        self._prepare_context(with_api_mapping=False)

        resource_definition = MagicMock()
        resource_definition.kind = 'BlahBlahBlah'

        with self.assertRaises(KuberentesMappingNotFoundError):
            utils.mapping_by_kind(resource_definition)

    def test_resource_definition_from_blueprint_kwargs(self):
        self._prepare_context(with_definition=False)

        definition = {
            'apiVersion': 'v1',
            'metadata': 'cc',
            'spec': 'dd',
            'kind': 'Deployment'
        }

        result = utils.resource_definition_from_blueprint(
            definition=definition
        )

        self.assertTrue(isinstance(result, KubernetesResourceDefinition))
        self.assertEquals(result.kind, 'Deployment')
        self.assertEquals(result.api_version, 'v1')
        self.assertEquals(result.metadata, 'cc')
        self.assertEquals(result.spec, 'dd')

    def test_resource_definition_from_blueprint_kwargs_no_kind(self):
        self._prepare_context(with_definition=False)

        definition = {
            'apiVersion': 'v1',
            'metadata': 'ccc',
            'spec': 'ddd'
        }

        result = utils.resource_definition_from_blueprint(
            definition=definition
        )

        self.assertTrue(isinstance(result, KubernetesResourceDefinition))
        self.assertEquals(result.kind, 'Pod')
        self.assertEquals(result.api_version, 'v1')
        self.assertEquals(result.metadata, 'ccc')
        self.assertEquals(result.spec, 'ddd')

    def test_resource_definition_from_blueprint_properties(self):
        self._prepare_context(with_definition=True, kind='Service')
        result = utils.resource_definition_from_blueprint()

        self.assertTrue(isinstance(result, KubernetesResourceDefinition))
        self.assertEquals(result.kind, 'Service')
        self.assertEquals(result.api_version, 'v1')
        self.assertEquals(result.metadata, 'c')
        self.assertEquals(result.spec, 'd')

    def test_resource_definition_from_blueprint_properties_no_kind(self):
        self._prepare_context(with_definition=True)
        result = utils.resource_definition_from_blueprint()

        self.assertTrue(isinstance(result, KubernetesResourceDefinition))
        self.assertEquals(result.kind, 'Pod')
        self.assertEquals(result.api_version, 'v1')
        self.assertEquals(result.metadata, 'c')
        self.assertEquals(result.spec, 'd')

    def test_resource_definition_from_blueprint_no_kind(self):
        _ctx = self._prepare_context(with_definition=True)
        _ctx._node.type = None
        current_ctx.set(_ctx)

        result = utils.resource_definition_from_blueprint()

        self.assertTrue(isinstance(result, KubernetesResourceDefinition))
        self.assertEquals(result.kind, '')
        self.assertEquals(result.api_version, 'v1')
        self.assertEquals(result.metadata, 'c')
        self.assertEquals(result.spec, 'd')

    def test_resource_definition_from_blueprint_error(self):
        self._prepare_context(with_definition=False)

        with self.assertRaises(KuberentesInvalidDefinitionError):
            utils.resource_definition_from_blueprint()

    def test_resource_definition_from_file_kwargs(self):
        self._prepare_context(with_definition=False)

        kwargs = {
            'file': {
                'resource_path': 'path'
            }
        }

        def _mocked_yaml_from_file(
            resource_path,
            target_path=None,
            template_variables=None
        ):
            if resource_path == 'path':
                return {
                    'apiVersion': 'v1',
                    'kind': 'PersistentVolume',
                    'metadata': 'a',
                    'spec': 'b'
                }

        with patch(
                'cloudify_kubernetes.utils._yaml_from_file',
                _mocked_yaml_from_file
        ):
            result = utils.resource_definition_from_file(
                **kwargs
            )

            self.assertTrue(isinstance(result, KubernetesResourceDefinition))
            self.assertEquals(result.kind, 'PersistentVolume')
            self.assertEquals(result.api_version, 'v1')
            self.assertEquals(result.metadata, 'a')
            self.assertEquals(result.spec, 'b')

    def test_resource_definition_from_file_properties(self):
        _ctx = MockCloudifyContext(
            node_id="test_id",
            node_name="test_name",
            deployment_id="test_name",
            properties={
                'file': {
                    'resource_path': 'path2'
                }
            },
            runtime_properties={
                'kubernetes': {
                    'metadata': {
                        'name': "kubernetes_id"
                    }
                }
            },
            relationships=[],
            operation={'retry_number': 0}
        )

        _ctx._node.type = 'cloudify.kubernetes.resources.Pod'

        current_ctx.set(_ctx)

        def _mocked_yaml_from_file(
            resource_path,
            target_path=None,
            template_variables=None
        ):
            if resource_path == 'path2':
                return {
                    'apiVersion': 'v1',
                    'kind': 'ReplicaSet',
                    'metadata': 'aa',
                    'spec': 'bb'
                }

        with patch(
                'cloudify_kubernetes.utils._yaml_from_file',
                _mocked_yaml_from_file
        ):
            result = utils.resource_definition_from_file()

            self.assertTrue(isinstance(result, KubernetesResourceDefinition))
            self.assertEquals(result.kind, 'ReplicaSet')
            self.assertEquals(result.api_version, 'v1')
            self.assertEquals(result.metadata, 'aa')
            self.assertEquals(result.spec, 'bb')

    def test_resource_definition_from_file_error(self):
        self._prepare_context(with_definition=False)

        with self.assertRaises(KuberentesInvalidDefinitionError):
            utils.resource_definition_from_file()


if __name__ == '__main__':
    unittest.main()
