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
from cloudify_kubernetes.k8s import (KuberentesApiInitializationFailedError,
                                     KuberentesAuthenticationError,
                                     KuberentesInvalidPayloadClassError,
                                     KuberentesInvalidApiMethodError,
                                     KuberentesInvalidApiClassError,
                                     KuberentesApiOperationError,
                                     KuberentesError)


class TestException(unittest.TestCase):

    def test_KuberentesApiInitializationFailedError(self):
        instance = KuberentesApiInitializationFailedError('message')
        self.assertTrue(isinstance(instance, KuberentesError))

    def test_KuberentesApiOperationError(self):
        instance = KuberentesApiOperationError('message')
        self.assertTrue(isinstance(instance, KuberentesError))

    def test_KuberentesAuthenticationError(self):
        instance = KuberentesAuthenticationError('message')
        self.assertTrue(isinstance(instance, KuberentesError))

    def test_KuberentesInvalidPayloadClassError(self):
        instance = KuberentesInvalidPayloadClassError('message')
        self.assertTrue(isinstance(instance, KuberentesError))

    def test_KuberentesInvalidApiClassError(self):
        instance = KuberentesInvalidApiClassError('message')
        self.assertTrue(isinstance(instance, KuberentesError))

    def test_KuberentesInvalidApiMethodError(self):
        instance = KuberentesInvalidApiMethodError('message')
        self.assertTrue(isinstance(instance, KuberentesError))

    def test_KuberentesError(self):
        instance = KuberentesError('message')
        self.assertTrue(isinstance(instance, Exception))


if __name__ == '__main__':
    unittest.main()
