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
import json
import unittest
from mock import (MagicMock, mock_open, patch)

from cloudify.state import current_ctx
from cloudify.mocks import MockCloudifyContext
from cloudify.exceptions import NonRecoverableError

from cloudify_kubernetes import utils
from cloudify.manager import DirtyTrackingDict
from cloudify_kubernetes.k8s.mapping import (
    KubernetesSingleOperationApiMapping,
    KubernetesApiMapping
)
from cloudify_kubernetes.k8s.exceptions import (
    KuberentesInvalidDefinitionError,
    KuberentesMappingNotFoundError
)
from cloudify_kubernetes.k8s.client import KubernetesResourceDefinition


file_resources = """
apiVersion: v1
kind: Service
metadata:
  name: foo
  namespace: bar
spec: c
---
apiVersion: v1
kind: Pod
metadata:
  name: bar
  namespace: foo
spec: d
---
"""


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
                mapping.update,
                KubernetesSingleOperationApiMapping
            )
        )

        self.assertEqual(mapping.update.api, 'CoreV1Api')
        self.assertEqual(mapping.update.method, 'patch_namespaced_pod')

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
            'allow_node_redefinition': True,
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
            runtime_properties=DirtyTrackingDict({
                'kubernetes': {
                    'metadata': {
                        'name': "kubernetes_id"
                    }
                }
            }),
            relationships=[],
            operation={'retry_number': 0}
        )

        _ctx.node.type_hierarchy = \
            ['cloudify.nodes.Root',
             'cloudify.kubernetes.resources.BlueprintDefinedResource',
             'cloudify.kubernetes.resources.Pod']

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
            'update': {
                'api': 'CoreV1Api',
                'method': 'patch_namespaced_pod',
            },
            'delete': {
                'api': 'CoreV1Api',
                'method': 'delete_namespaced_pod',
                'payload': 'V1DeleteOptions'
            },
        }

    def test_retrieve_path(self):
        self.assertEquals(
            utils.retrieve_path({'file': {'resource_path': 'path'}}),
            'path'
        )

        self.assertEquals(
            utils.retrieve_path({'file': {}}),
            ''
        )

        self.assertEquals(
            utils.retrieve_path({}),
            ''
        )

    def test_yaml_from_files(self):
        yaml_data = 'test: \n  a: 1 \n  b: 2\n---'

        _ctx = MockCloudifyContext()
        _ctx.download_resource_and_render = \
            lambda resource_path, target_path, template_variables: \
            'local_path' if resource_path == 'path' else None

        current_ctx.set(_ctx)

        with patch(
                'cloudify_kubernetes.utils.open',
                mock_open(read_data=yaml_data)
        ) as file_mock:
            result = utils._yaml_from_files('path')

            self.assertEquals(list(result),
                              [{'test': {'a': 1, 'b': 2, }}, None])
            file_mock.assert_called_once_with('local_path', 'rb')

    def test_mapping_by_data_kwargs(self):
        self._prepare_context(with_api_mapping=False)
        mapping = self._prepare_mapping()
        self._assert_mapping(
            utils.mapping_by_data(api_mapping=mapping)
        )

    def test_mapping_by_data_properties(self):
        self._prepare_context(with_api_mapping=True)
        self._assert_mapping(
            utils.mapping_by_data()
        )

    def test_mapping_by_data_error(self):
        self._prepare_context(with_api_mapping=False)

        with self.assertRaises(KuberentesMappingNotFoundError):
            utils.mapping_by_data()

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
        self._prepare_context(with_definition=True)

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
        self._prepare_context(with_definition=True)

        result = utils.resource_definition_from_blueprint()

        self.assertTrue(isinstance(result, KubernetesResourceDefinition))
        self.assertEquals(result.kind, 'Pod')
        self.assertEquals(result.api_version, 'v1')
        self.assertEquals(result.metadata, 'c')
        self.assertEquals(result.spec, 'd')

    def test_resource_definition_from_blueprint_error(self):
        self._prepare_context(with_definition=False)

        with self.assertRaises(KuberentesInvalidDefinitionError):
            utils.resource_definition_from_blueprint()

    def test_resource_definitions_from_file_kwargs(self):
        self._prepare_context(with_definition=False)

        kwargs = {
            'file': {
                'resource_path': 'path'
            }
        }

        with patch("cloudify_kubernetes.utils.open",
                   mock_open(read_data=file_resources)):
            with patch('cloudify.ctx.download_resource_and_render'):
                with patch('os.path.isfile'):
                    with patch('os.path.getsize'):
                        result = utils.resource_definitions_from_file(**kwargs)

            self.assertTrue(isinstance(result[0],
                                       KubernetesResourceDefinition))
            self.assertEquals(result[0].kind, 'Service')
            self.assertEquals(result[0].api_version, 'v1')
            self.assertEquals(result[0].metadata,
                              {'namespace': 'bar', 'name': 'foo'})
            self.assertEquals(result[0].spec, 'c')

            self.assertTrue(isinstance(result[1],
                                       KubernetesResourceDefinition))
            self.assertEquals(result[1].kind, 'Pod')
            self.assertEquals(result[1].api_version, 'v1')
            self.assertEquals(result[1].metadata,
                              {'namespace': 'foo', 'name': 'bar'})
            self.assertEquals(result[1].spec, 'd')

    def test_resource_definitions_from_file_properties(self):
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

        _ctx.node.type_hierarchy = \
            ['cloudify.nodes.Root',
             'cloudify.kubernetes.resources.BlueprintDefinedResource',
             'cloudify.kubernetes.resources.Pod']

        current_ctx.set(_ctx)

        def _mocked_yaml_from_files(
            resource_path,
            target_path=None,
            template_variables=None
        ):
            if resource_path == 'path2':
                return [{
                    'apiVersion': 'v1',
                    'kind': 'ReplicaSet',
                    'metadata': 'aa',
                    'spec': 'bb'
                }]

        with patch(
                'cloudify_kubernetes.utils._yaml_from_files',
                _mocked_yaml_from_files
        ):
            result = utils.resource_definitions_from_file()

            self.assertTrue(isinstance(result[0],
                                       KubernetesResourceDefinition))
            self.assertEquals(result[0].kind, 'ReplicaSet')
            self.assertEquals(result[0].api_version, 'v1')
            self.assertEquals(result[0].metadata, 'aa')
            self.assertEquals(result[0].spec, 'bb')

    def test_resource_definitions_from_file_error(self):
        self._prepare_context(with_definition=False)

        with self.assertRaises(NonRecoverableError):
            utils.resource_definitions_from_file()

    def test_get_definition_object(self):
        # with type hierarchy
        self._prepare_context(with_definition=True)
        self.assertEqual(
            utils.get_definition_object(
                definition=json.loads(
                    json.dumps({'spec': {'a': 'b'}})),
                definitions_additions=json.loads(
                    json.dumps({'spec': {'c': 'd'}}))
            ),
            {
                'kind': 'cloudify.kubernetes.resources.Pod',
                'spec': {
                    'a': 'b',
                    'c': 'd'
                }
            }
        )
        # without type hierarchy
        _ctx = self._prepare_context(with_definition=True)
        _ctx.node.type_hierarchy = ['cloudify.nodes.Root']
        self.assertEqual(
            utils.get_definition_object(
                definition={'spec': {'a': 'b'}},
                definitions_additions={'spec': {'c': 'd'}}
            ),
            {
                'kind': '',
                'spec': {
                    'a': 'b',
                    'c': 'd'
                }
            }
        )

    def test_resource_definition_storage_from_blueprint(self):
        _ctx = self._prepare_context(with_definition=True)
        definition = {
            'apiVersion': 'v1',
            'metadata': 'cc',
            'spec': 'dd',
            'kind': 'Deployment'
        }
        result_from_blueprint = utils.resource_definition_from_blueprint(
            definition=definition
        )
        utils.store_resource_definition(result_from_blueprint)
        self.assertIn('__resource_definitions',
                      _ctx.instance.runtime_properties)
        self.assertDictEqual(
            definition,
            _ctx.instance.runtime_properties['__resource_definitions'][0]
        )
        mock_mapping = KubernetesApiMapping(**self._prepare_mapping())
        result_from_storage, mapping_from_storage = \
            utils.retrieve_stored_resource(result_from_blueprint,
                                           mock_mapping)
        self.assertEqual(result_from_blueprint, result_from_storage)
        self.assertTrue(isinstance(
            mapping_from_storage, KubernetesApiMapping))

    def test_resource_definition_storage_from_file(self):
        _ctx = self._prepare_context(with_definition=False)

        kwargs = {
            'file': {
                'resource_path': 'path'
            }
        }

        definition1 = json.loads(json.dumps({
            'apiVersion': 'v1',
            'metadata': {'name': 'MyDeployment'},
            'spec': 'dd',
            'kind': 'Deployment'
        }))

        definition2 = json.loads(json.dumps({
            'apiVersion': 'v1',
            'metadata': {'name': 'MyService'},
            'spec': 'ss',
            'kind': 'Service'
        }))

        definition3 = json.loads(json.dumps({
            'apiVersion': 'v1',
            'metadata': {'name': 'MyIngress'},
            'spec': 'ii',
            'kind': 'Ingress'
        }))

        def _mocked_yaml_from_files(
            resource_path,
            target_path=None,
            template_variables=None
        ):
            if resource_path == 'path':
                return [definition1, definition2, definition3]

        with patch(
                'cloudify_kubernetes.utils._yaml_from_files',
                _mocked_yaml_from_files
        ):
            results_from_file = utils.resource_definitions_from_file(**kwargs)
            for rs in results_from_file:
                utils.store_resource_definition(rs)
            self.assertIn('__resource_definitions',
                          _ctx.instance.runtime_properties)
            self.assertDictEqual(
                definition1,
                _ctx.instance.runtime_properties['__resource_definitions'][0]
            )
            self.assertDictEqual(
                definition2,
                _ctx.instance.runtime_properties['__resource_definitions'][1]
            )
            self.assertDictEqual(
                definition3,
                _ctx.instance.runtime_properties['__resource_definitions'][2]
            )
            results_from_file.reverse()
            mock_mapping = KubernetesApiMapping(**self._prepare_mapping())
            for result_from_file in results_from_file:
                result_from_storage, _ = \
                    utils.retrieve_stored_resource(result_from_file,
                                                   mock_mapping)
                self.assertEqual(result_from_file, result_from_storage)

    def test_set_namespace(self):
        self._prepare_context(with_definition=False)
        self.assertIsNone(utils.set_namespace({'namespace': 'default'}))
        kwargs = {}
        utils.set_namespace(kwargs)
        self.assertIn('namespace', kwargs)
        del kwargs['namespace']
        resource = KubernetesResourceDefinition(
            'foo', 'v1', {'name': 'bar'}, 'b')
        utils.set_namespace(kwargs, resource)
        self.assertIn('namespace', kwargs)

    def test_tempfiles_for_certs_and_keys(self):
        config = {
            'api_options': {
                'host': 'foo',
                'api_key': 'bar',
                'verify_ssl': True,
                'ssl_ca_cert': 'baz',
                'cert_file': 'taco',
                'key_file': 'bell'
            }
        }
        config = utils.create_tempfiles_for_certs_and_keys(config)
        for key in utils.CERT_KEYS:
            assert os.path.isfile(config['api_options'][key])
        utils.delete_tempfiles_for_certs_and_keys(config)
        for key in utils.CERT_KEYS:
            assert os.path.exists(config['api_options'][key]) is False

    def test_handle_existing_resource(self):
        _ctx = self._prepare_context()
        definition = MagicMock()
        definition.to_dict.return_value = {'foo': 'bar'}

        resource_exists = False
        _ctx.node.properties['use_external_resource'] = False
        _ctx.node.properties['create_if_missing'] = False
        _ctx.node.properties['use_if_exists'] = False
        current_ctx.set(_ctx)
        utils.handle_existing_resource(resource_exists, definition)
        # The resource doesn't exist and it's not supposed to. So we perform.
        self.assertTrue(_ctx.instance.runtime_properties['__perform_task'])

        resource_exists = False
        _ctx.node.properties['use_external_resource'] = True
        _ctx.node.properties['create_if_missing'] = True
        _ctx.node.properties['use_if_exists'] = False
        current_ctx.set(_ctx)
        utils.handle_existing_resource(resource_exists, definition)
        # The resource doesn't exist. It should, and we want to create anyway.
        self.assertTrue(_ctx.instance.runtime_properties['__perform_task'])

        resource_exists = True
        utils.handle_existing_resource(resource_exists, definition)
        # The resource exists. It should. So we don't want to recreate it.
        self.assertFalse(_ctx.instance.runtime_properties['__perform_task'])

        resource_exists = False
        _ctx.node.properties['use_external_resource'] = True
        _ctx.node.properties['create_if_missing'] = False
        _ctx.node.properties['use_if_exists'] = False
        current_ctx.set(_ctx)
        utils.handle_existing_resource(resource_exists, definition)
        # The resource doesn't exist. It should, but we wont create it.
        self.assertFalse(_ctx.instance.runtime_properties['__perform_task'])

        resource_exists = True
        _ctx.node.properties['use_external_resource'] = True
        _ctx.node.properties['create_if_missing'] = False
        _ctx.node.properties['use_if_exists'] = False
        current_ctx.set(_ctx)
        utils.handle_existing_resource(resource_exists, definition)
        # The resource exists. It should. So we don't want to do anything.
        self.assertFalse(_ctx.instance.runtime_properties['__perform_task'])

        resource_exists = True
        _ctx.node.properties['use_external_resource'] = True
        _ctx.node.properties['create_if_missing'] = True
        _ctx.node.properties['use_if_exists'] = False
        current_ctx.set(_ctx)
        utils.handle_existing_resource(resource_exists, definition)
        # The resource exists. It should. We say create anyway. But we still
        # should not.
        self.assertFalse(_ctx.instance.runtime_properties['__perform_task'])

        resource_exists = True
        _ctx.node.properties['use_external_resource'] = False
        _ctx.node.properties['create_if_missing'] = False
        _ctx.node.properties['use_if_exists'] = True
        current_ctx.set(_ctx)
        utils.handle_existing_resource(resource_exists, definition)
        # The resource exists. It shouldn't. We say use anyway. No create.
        self.assertFalse(_ctx.instance.runtime_properties['__perform_task'])


if __name__ == '__main__':
    unittest.main()
