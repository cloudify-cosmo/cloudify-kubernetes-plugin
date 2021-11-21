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

from ..k8s.exceptions import KuberentesMappingNotFoundError
from ..k8s.mapping import (
    get_mapping,
    KubernetesApiMapping,
    KubernetesSingleOperationApiMapping)


class TestMapping(unittest.TestCase):

    def test_KubernetesSingleOperationApiMapping_alternates(self):
        self.maxDiff = None
        # These outcomes are dependent on the version of the Kubernetes Python
        # library. If you have updated it, they may have changed.

        def check_alternate_mapping(alternates, expected):
            exceptions = []
            for alternate in alternates:
                if alternate:
                    try:
                        self.assertIn(
                            (alternate.api, alternate.payload), expected)
                    except AssertionError as e:
                        exceptions.append(e)
            if exceptions:
                raise AssertionError(
                    'These were raised: {}'.format(exceptions))

        expected_alternates = [
            [
                ('NodeV1alpha1Api', 'V1alpha1RuntimeClass'),
            ],
            [
                ('NetworkingV1Api', 'V1Ingress'),
                ('ExtensionsV1beta1Api', 'ExtensionsV1beta1Ingress'),
            ],
            [
                ('BatchV2alpha1Api', 'V2alpha1CronJob')
            ],
            [
                ('StorageV1Api', 'V1StorageClass'),
            ],
            [
                ('RbacAuthorizationV1alpha1Api', 'V1alpha1ClusterRole'),
                ('RbacAuthorizationV1beta1Api', 'V1beta1ClusterRole')
            ],
            [
                ('RbacAuthorizationV1alpha1Api', None),
                ('RbacAuthorizationV1beta1Api', None)
            ],
            [
                ('RbacAuthorizationV1alpha1Api', None),
                ('RbacAuthorizationV1beta1Api', None)
            ],
            [
                ('RbacAuthorizationV1alpha1Api', 'V1DeleteOptions'),
                ('RbacAuthorizationV1beta1Api', 'V1DeleteOptions')
            ],
            [],
            [],
            [
                ('AdmissionregistrationV1beta1Api', 'V1DeleteOptions')
            ]
        ]
        operation_mappings = [
            KubernetesSingleOperationApiMapping(
                api='NodeV1beta1Api',
                method='create_runtime_class',
                payload='V1beta1RuntimeClass'
            ).alternates,
            KubernetesSingleOperationApiMapping(
                api='NetworkingV1beta1Api',
                method='create_namespaced_ingress',
                payload='NetworkingV1beta1Ingress'
            ).alternates,
            KubernetesSingleOperationApiMapping(
                api='BatchV1beta1Api',
                method='create_namespaced_cron_job',
                payload='V1beta1CronJob'
            ).alternates,
            KubernetesSingleOperationApiMapping(
                api='StorageV1beta1Api',
                method='create_storage_class',
                payload='V1beta1StorageClass'
            ).alternates,
            KubernetesSingleOperationApiMapping(
                api='RbacAuthorizationV1Api',
                method='create_cluster_role',
                payload='V1beta1ClusterRole'
            ).alternates,
            KubernetesSingleOperationApiMapping(
                api='RbacAuthorizationV1Api',
                method='read_cluster_role',
            ).alternates,
            KubernetesSingleOperationApiMapping(
                api='RbacAuthorizationV1Api',
                method='patch_cluster_role',
            ).alternates,
            KubernetesSingleOperationApiMapping(
                api='RbacAuthorizationV1Api',
                method='delete_cluster_role',
                payload='V1DeleteOptions'
            ).alternates,
            KubernetesSingleOperationApiMapping(
                api='CoreV1Api',
                method='patch_namespaced_service'
            ).alternates,
            KubernetesSingleOperationApiMapping(
                api='CoreV1Api',
                method='read_namespaced_persistent_volume_claim',
            ).alternates,
            KubernetesSingleOperationApiMapping(
                api='AdmissionregistrationV1Api',
                method='delete_validating_webhook_configuration',
                payload='V1DeleteOptions'
            ).alternates
        ]
        for i, operation_mapping in enumerate(operation_mappings):
            check_alternate_mapping(operation_mapping, expected_alternates[i])

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
            update='update',
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
            update={
                'api': 'u_api',
                'method': 'u_method',
                'payload': 'u_payload'
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
                instance.update,
                KubernetesSingleOperationApiMapping
            )
        )

        self.assertEqual(instance.update.api, 'u_api')
        self.assertEqual(instance.update.method, 'u_method')
        self.assertEqual(instance.update.payload, 'u_payload')

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
                mapping.update,
                KubernetesSingleOperationApiMapping
            )
        )

        self.assertEqual(mapping.update.api, 'CoreV1Api')
        self.assertEqual(mapping.update.method, 'patch_namespaced_pod')
        self.assertEqual(mapping.update.payload, None)

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
