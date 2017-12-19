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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import unittest
from mock import MagicMock
from kubernetes.client.rest import ApiException

from cloudify_kubernetes.k8s.operations import (KubernetesCreateOperation,
                                                KubernetesReadOperation,
                                                KubernetesUpdateOperation,
                                                KubernetesDeleteOperation)
from cloudify_kubernetes.k8s.exceptions import KuberentesApiOperationError


class TestKubernetesCreateOperation(unittest.TestCase):

    def test_init(self):
        instance = KubernetesCreateOperation("api_method", ['a', 'b'])
        self.assertEqual(instance.api_method, 'api_method')
        self.assertEqual(instance.api_method_arguments_names, ['a', 'b'])

    def test_prepare_arguments(self):
        instance = KubernetesCreateOperation("api_method", ['a', 'b'])
        self.assertEqual(
            instance._prepare_arguments({'a': 'c', 'b': 'd'}),
            {'a': 'c', 'b': 'd'}
        )
        self.assertEqual(
            instance._prepare_arguments({'a': 'd', 'b': 'e', 'c': 'f'}),
            {'a': 'd', 'b': 'e'}
        )

        with self.assertRaises(KuberentesApiOperationError) as error:
            instance._prepare_arguments({'a': 'd', 'c': 'f'})

        self.assertEqual(
            str(error.exception),
            "Invalid input data for execution of Kubernetes API method: "
            "input argument b is not defined but is mandatory"
        )

    def test_execute(self):
        call_mock = MagicMock(return_value="!")
        instance = KubernetesCreateOperation(call_mock, ['a', 'b'])

        self.assertEqual(
            instance.execute({'a': 'd', 'b': 'e', 'c': 'f'}),
            "!"
        )
        call_mock.assert_called_with(a='d', b='e')

    def test_execute_ApiException(self):
        call_mock = MagicMock(side_effect=ApiException("!"))
        instance = KubernetesCreateOperation(call_mock, ['a', 'b'])

        with self.assertRaises(KuberentesApiOperationError) as error:
            instance.execute({'a': 'd', 'b': 'e', 'c': 'f'})

        self.assertEqual(
            str(error.exception),
            "Operation execution failed. Exception during Kubernetes API "
            "call: (!)\nReason: None\n"
        )
        call_mock.assert_called_with(a='d', b='e')


class TestKubernetesReadOperation(unittest.TestCase):

    def test_init(self):
        instance = KubernetesReadOperation("api_method", ['a', 'b'])
        self.assertEqual(instance.api_method, 'api_method')
        self.assertEqual(instance.api_method_arguments_names, ['a', 'b'])

    def test_prepare_arguments(self):
        instance = KubernetesReadOperation("api_method", ['a', 'b'])
        self.assertEqual(
            instance._prepare_arguments({'a': 'c', 'b': 'd'}),
            {'a': 'c', 'b': 'd'}
        )
        self.assertEqual(
            instance._prepare_arguments({
                'a': 'd', 'b': 'e', 'exact': 'f', 'export': 'g', 'h': 'i'
            }),
            {'a': 'd', 'b': 'e', 'exact': 'f', 'export': 'g'}
        )

        with self.assertRaises(KuberentesApiOperationError) as error:
            instance._prepare_arguments({'a': 'd', 'c': 'f'})

        self.assertEqual(
            str(error.exception),
            "Invalid input data for execution of Kubernetes API method: "
            "input argument b is not defined but is mandatory"
        )


class TestKubernetesUpdateOperation(unittest.TestCase):

    def test_init(self):
        instance = KubernetesUpdateOperation("api_method", ['a', 'b'])
        self.assertEqual(instance.api_method, 'api_method')
        self.assertEqual(instance.api_method_arguments_names, ['a', 'b'])

    def test_prepare_arguments(self):
        instance = KubernetesUpdateOperation("api_method", ['a', 'b'])
        self.assertEqual(
            instance._prepare_arguments({'a': 'c', 'b': 'd'}),
            {'a': 'c', 'b': 'd'}
        )
        self.assertEqual(
            instance._prepare_arguments({'a': 'd', 'b': 'e', 'c': 'f'}),
            {'a': 'd', 'b': 'e'}
        )

        with self.assertRaises(KuberentesApiOperationError) as error:
            instance._prepare_arguments({'a': 'd', 'c': 'f'})

        self.assertEqual(
            str(error.exception),
            "Invalid input data for execution of Kubernetes API method: "
            "input argument b is not defined but is mandatory"
        )

    def test_execute(self):
        call_mock = MagicMock(return_value="!")
        instance = KubernetesUpdateOperation(call_mock, ['a', 'b'])

        self.assertEqual(
            instance.execute({'a': 'd', 'b': 'e', 'c': 'f'}),
            "!"
        )
        call_mock.assert_called_with(a='d', b='e')

    def test_execute_ApiException(self):
        call_mock = MagicMock(side_effect=ApiException("!"))
        instance = KubernetesUpdateOperation(call_mock, ['a', 'b'])

        with self.assertRaises(KuberentesApiOperationError) as error:
            instance.execute({'a': 'd', 'b': 'e', 'c': 'f'})

        self.assertEqual(
            str(error.exception),
            "Operation execution failed. Exception during Kubernetes API "
            "call: (!)\nReason: None\n"
        )
        call_mock.assert_called_with(a='d', b='e')


class TestKubernetesDeleteOperation(unittest.TestCase):

    def test_init(self):
        instance = KubernetesDeleteOperation("api_method", ['a', 'b'])
        self.assertEqual(instance.api_method, 'api_method')
        self.assertEqual(instance.api_method_arguments_names, ['a', 'b'])

    def test_prepare_arguments(self):
        instance = KubernetesDeleteOperation("api_method", ['a', 'b'])
        self.assertEqual(
            instance._prepare_arguments({'a': 'c', 'b': 'd'}),
            {'a': 'c', 'b': 'd'}
        )
        self.assertEqual(
            instance._prepare_arguments({
                'a': 'd', 'b': 'e', 'exact': 'f',
                'grace_period_seconds': 'g', 'propagation_policy': 'i'
            }), {
                'a': 'd', 'b': 'e', 'grace_period_seconds': 'g',
                'propagation_policy': 'i'
            }
        )

        with self.assertRaises(KuberentesApiOperationError) as error:
            instance._prepare_arguments({'a': 'd', 'c': 'f'})

        self.assertEqual(
            str(error.exception),
            "Invalid input data for execution of Kubernetes API method: "
            "input argument b is not defined but is mandatory"
        )


if __name__ == '__main__':
    unittest.main()
