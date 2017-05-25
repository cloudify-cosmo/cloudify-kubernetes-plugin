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
from cloudify_kubernetes.k8s import (KubernetesApiMapping,
                                     KubernetesResourceDefinition)


class TestData(unittest.TestCase):

    def test_KubernetesApiMapping(self):
        instance = KubernetesApiMapping(read='read', create='create',
                                        delete='delete')

        self.assertEqual(instance.read, 'read')
        self.assertEqual(instance.create, 'create')
        self.assertEqual(instance.delete, 'delete')

    def test_KubernetesResourceDefinition(self):
        instance = KubernetesResourceDefinition(kind="1.2.3.4",
                                                apiVersion="v1",
                                                metadata="metadata",
                                                spec="spec")

        self.assertEqual(instance.kind, "4")
        self.assertEqual(instance.api_version, "v1")
        self.assertEqual(instance.metadata, "metadata")
        self.assertEqual(instance.spec, "spec")


if __name__ == '__main__':
    unittest.main()
