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

from cloudify_kubernetes.k8s.exceptions import KuberentesMappingNotFoundError
from cloudify_kubernetes.k8s.mapping import (
    KubernetesSingleOperationApiMapping,
    KubernetesApiMapping,
    get_mapping
)


class TestMapping(unittest.TestCase):

    def test_KubernetesSingleOperationApiMapping(self):
        instance = KubernetesSingleOperationApiMapping(
            api='api',
            method='method',
            payload='payload'
        )

        self.assertEqual(instance.api, 'api')
        self.assertEqual(instance.method, 'method')
        self.assertEqual(instance.payload, 'payload')

    def test_KubernetesSingleOperationApiMapping_no_payload(self):
        instance = KubernetesSingleOperationApiMapping(
            api='api',
            method='method',
        )

        self.assertEqual(instance.api, 'api')
        self.assertEqual(instance.method, 'method')
        self.assertEqual(instance.payload, None)

    def test_KubernetesApiMapping(self):
        instance = KubernetesApiMapping(
            read='read',
            create='create',
            delete='delete'
        )

        self.assertEqual(instance.read, 'read')
        self.assertEqual(instance.create, 'create')
        self.assertEqual(instance.delete, 'delete')

    def test_KubernetesApiMapping_from_dict(self):
        instance = KubernetesApiMapping(
            read={
                'api': 'r_api',
                'method': 'r_method',
                'payload': 'r_payload'
            },
            create={
                'api': 'c_api',
                'method': 'c_method',
                'payload': 'c_payload'
            },
            delete={
                'api': 'd_api',
                'method': 'd_method',
                'payload': 'd_payload'
            }
        )

        self.assertTrue(
            isinstance(
                instance.read,
                KubernetesSingleOperationApiMapping
            )
        )

        self.assertEqual(instance.read.api, 'r_api')
        self.assertEqual(instance.read.method, 'r_method')
        self.assertEqual(instance.read.payload, 'r_payload')

        self.assertTrue(
            isinstance(
                instance.create,
                KubernetesSingleOperationApiMapping
            )
        )

        self.assertEqual(instance.create.api, 'c_api')
        self.assertEqual(instance.create.method, 'c_method')
        self.assertEqual(instance.create.payload, 'c_payload')

        self.assertTrue(
            isinstance(
                instance.delete,
                KubernetesSingleOperationApiMapping
            )
        )

        self.assertEqual(instance.delete.api, 'd_api')
        self.assertEqual(instance.delete.method, 'd_method')
        self.assertEqual(instance.delete.payload, 'd_payload')

    def test_get_mapping(self):
        mapping = get_mapping('Pod')

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

    def test_get_mapping_no_entry(self):
        with self.assertRaises(KuberentesMappingNotFoundError):
            get_mapping('BlahBlahBlah')


if __name__ == '__main__':
    unittest.main()
