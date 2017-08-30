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
from mock import MagicMock

from kubernetes.client.rest import ApiException
from cloudify_kubernetes.k8s import (CloudifyKubernetesClient,
                                     KuberentesInvalidPayloadClassError,
                                     KuberentesInvalidApiClassError,
                                     KuberentesInvalidApiMethodError,
                                     KubernetesResourceDefinition,
                                     KuberentesApiOperationError)


class TestClient(unittest.TestCase):

    def test_init(self):
        logger = MagicMock()
        api_configuration = MagicMock()
        api_configuration.prepare_api = MagicMock(return_value="APi")
        instance = CloudifyKubernetesClient(logger, api_configuration)
        self.assertEqual(instance.logger, logger)
        self.assertEqual(instance.api, "APi")

    def test_name(self):
        logger = MagicMock()
        api_configuration = MagicMock()
        api_mock = MagicMock()
        api_mock.__class__.__name__ = "ClassName"
        api_configuration.prepare_api = MagicMock(return_value=api_mock)

        instance = CloudifyKubernetesClient(logger, api_configuration)
        self.assertEqual(instance._name, "ClassName")

    def test_prepare_payload_InvalidPayload(self):
        logger = MagicMock()
        api_configuration = MagicMock()

        class FakeApi(object):

            def __getattr__(self, name):
                raise AttributeError()

        api_configuration.prepare_api = MagicMock(return_value=FakeApi())

        instance = CloudifyKubernetesClient(logger, api_configuration)
        with self.assertRaises(KuberentesInvalidPayloadClassError) as error:
            instance._prepare_payload('unknown_attribute', MagicMock())

        self.assertEqual(
            str(error.exception),
            "Cannot create instance of Kubernetes API payload class: "
            "unknown_attribute. Class not supported by client FakeApi"
        )

    def test_prepare_api_method_InvalidApiClass(self):
        logger = MagicMock()
        api_configuration = MagicMock()

        class FakeApi(object):

            def __getattr__(self, name):
                raise AttributeError()

        api_configuration.prepare_api = MagicMock(return_value=FakeApi())

        instance = CloudifyKubernetesClient(logger, api_configuration)
        with self.assertRaises(KuberentesInvalidApiClassError) as error:
            instance._prepare_api_method('unknown_attribute',
                                         'other_attribute')

        self.assertEqual(
            str(error.exception),
            "Cannot create instance of Kubernetes API class: "
            "unknown_attribute. Class not supported by client FakeApi"
        )

    def test_prepare_api_method_InvalidApiMethod(self):
        logger = MagicMock()
        api_configuration = MagicMock()

        class FakeApi(object):

            def __getattr__(self, name):
                raise AttributeError()

        mock_api = MagicMock()
        mock_api.attribute = MagicMock(return_value=FakeApi())

        api_configuration.prepare_api = MagicMock(return_value=mock_api)

        instance = CloudifyKubernetesClient(logger, api_configuration)
        with self.assertRaises(KuberentesInvalidApiMethodError) as error:
            instance._prepare_api_method('attribute', 'other_attribute')

        self.assertEqual(
            str(error.exception),
            "Method other_attribute not supported by Kubernetes API class "
            "attribute"
        )

    def test_execute_ApiException(self):
        logger = MagicMock()
        api_configuration = MagicMock()

        mock_api = MagicMock()
        api_configuration.prepare_api = MagicMock(return_value=mock_api)
        operation_mock = MagicMock()
        operation_mock.execute = MagicMock(side_effect=ApiException())

        instance = CloudifyKubernetesClient(logger, api_configuration)
        with self.assertRaises(KuberentesApiOperationError) as error:
            instance._execute(operation_mock, {'a': 'b'})

        operation_mock.execute.assert_called_with({'a': 'b'})
        self.assertEqual(
            str(error.exception),
            "Exception during Kubernetes API call: (None)\nReason: None\n"
        )

    def _prepere_mocks(self):
        logger = MagicMock()
        api_configuration = MagicMock()

        mock_api = MagicMock()

        client_api = MagicMock()

        def del_func(body, name, first):
            return (body, name, first)

        def read_func(name, first):
            return (name, first)

        def create_func(body, first):
            mock = MagicMock()
            mock.to_dict = MagicMock(return_value={
                'body': body, 'first': first
            })
            return mock

        client_api.delete = del_func
        client_api.read = read_func
        client_api.create = create_func

        mock_api.api_client_version = MagicMock(
            return_value=client_api
        )
        mock_api.api_payload_version = MagicMock(
            return_value={'payload_param': 'payload_value'}
        )

        api_configuration.prepare_api = MagicMock(return_value=mock_api)

        operation_mock = MagicMock()
        operation_mock.execute = MagicMock(side_effect=ApiException())

        mappingMock = MagicMock()

        mappingMock.create = MagicMock()
        mappingMock.create.payload = 'api_payload_version'
        mappingMock.create.api = 'api_client_version'
        mappingMock.create.method = 'create'

        mappingMock.read = MagicMock()
        mappingMock.read.api = 'api_client_version'
        mappingMock.read.method = 'read'

        mappingMock.delete = MagicMock()
        mappingMock.delete.api = 'api_client_version'
        mappingMock.delete.method = 'delete'

        return CloudifyKubernetesClient(logger, api_configuration), mappingMock

    def test_execute_create_resource(self):

        instance, mappingMock = self._prepere_mocks()

        self.assertEqual(
            instance.create_resource(
                mappingMock,
                KubernetesResourceDefinition(kind="1.2.3.4",
                                             apiVersion="v1",
                                             metadata="metadata",
                                             spec="spec"),
                {'first': 'b'}
            ).to_dict(),
            {
                'body': {'payload_param': 'payload_value'},
                'first': 'b'
            }
        )

    def test_execute_delete_resource(self):

        instance, mappingMock = self._prepere_mocks()

        self.assertEqual(
            instance.delete_resource(
                mappingMock, "resource_id", {'first': 'b'}
            ),
            ({}, 'resource_id', 'b')
        )

    def test_execute_read_resource(self):

        instance, mappingMock = self._prepere_mocks()

        self.assertEqual(
            instance.read_resource(
                mappingMock, "resource_id", {'first': 'b'}
            ),
            ('resource_id', 'b')
        )


class TestKubernetesResourceDefinition(unittest.TestCase):
    def test_KubernetesResourceDefinitionGeneral(self):
        instance = KubernetesResourceDefinition(kind="1.2.3.4",
                                                apiVersion="v1",
                                                metadata="metadata",
                                                spec="spec")

        self.assertEqual(instance.kind, "4")
        self.assertEqual(instance.api_version, "v1")
        self.assertEqual(instance.metadata, "metadata")
        self.assertEqual(instance.spec, "spec")

    def test_KubernetesResourceDefinitionStorage(self):
        instance = KubernetesResourceDefinition(kind="1.2.3.4",
                                                apiVersion="v1",
                                                metadata="metadata",
                                                parameters="parameters",
                                                provisioner="provisioner")

        self.assertEqual(instance.kind, "4")
        self.assertEqual(instance.api_version, "v1")
        self.assertEqual(instance.metadata, "metadata")
        self.assertEqual(instance.parameters, "parameters")
        self.assertEqual(instance.provisioner, "provisioner")


if __name__ == '__main__':
    unittest.main()
