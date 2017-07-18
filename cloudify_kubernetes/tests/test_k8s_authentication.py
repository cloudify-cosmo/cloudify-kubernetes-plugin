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
from mock import MagicMock, patch

from cloudify_kubernetes.k8s.authentication import (
    KubernetesApiAuthentication,
    GCPServiceAccountAuthentication,
    KubernetesApiAuthenticationVariants
)
from cloudify_kubernetes.k8s.exceptions import KuberentesAuthenticationError


class BaseTestK8SAuthentication(unittest.TestCase):
    def _mock_api(self):
        api_key = {}
        mock_api_key = MagicMock()
        mock_api_key.__setitem__.side_effect = api_key.__setitem__

        api_key_prefix = {}
        mock_api_key_prefix = MagicMock()
        mock_api_key_prefix.__setitem__.side_effect = \
            api_key_prefix.__setitem__

        mock_configuration = MagicMock(
            api_key=mock_api_key,
            api_key_prefix=mock_api_key_prefix
        )
        mock_api = MagicMock(configuration=mock_configuration)

        return api_key, api_key_prefix, mock_api


class TestKubernetesApiAuthentication(BaseTestK8SAuthentication):

    def test_KubernetesApiAuthentication(self):
        mock_api = MagicMock()
        instance = KubernetesApiAuthentication('logger', 'conf')

        self.assertEqual(instance.logger, 'logger')
        self.assertEqual(instance.authentication_data, 'conf')
        self.assertFalse(instance._do_authenticate(mock_api))

        with self.assertRaises(KuberentesAuthenticationError):
            instance.authenticate(mock_api)


class TestGCPServiceAccountAuthentication(BaseTestK8SAuthentication):

    def test_GCPServiceAccountAuthentication_ErrorNoData(self):
        mock_api = MagicMock()
        mock_logger = MagicMock()

        instance = GCPServiceAccountAuthentication(
            mock_logger,
            {},
        )

        with self.assertRaises(KuberentesAuthenticationError):
            instance.authenticate(mock_api)

    def test_GCPServiceAccountAuthentication(self):
        mock_logger = MagicMock()

        api_key, api_key_prefix, mock_api = self._mock_api()

        token = 'token'
        access_token_mock = MagicMock(access_token=token)
        mock_credentials = MagicMock()
        mock_credentials.get_access_token = MagicMock(
            return_value=access_token_mock
        )

        instance = GCPServiceAccountAuthentication(
            mock_logger,
            {'gcp_service_account': {'blah': 'blah'}},
        )

        with patch(
            'oauth2client.service_account.'
            'ServiceAccountCredentials.from_json_keyfile_dict',
            MagicMock(return_value=mock_credentials)
        ):
            instance.authenticate(mock_api)

        self.assertEquals(token, api_key['authorization'])
        self.assertEquals('Bearer', api_key_prefix['authorization'])


class TestKubernetesAuthenticationVariants(BaseTestK8SAuthentication):

    def test_KubernetesApiAuthenticationVariants_Error(self):
        api_key, api_key_prefix, mock_api = self._mock_api()
        mock_logger = MagicMock()

        instance = KubernetesApiAuthenticationVariants(
            mock_logger,
            {},
        )

        instance.authenticate(mock_api)

        self.assertFalse('authorization' in api_key)
        self.assertFalse('authorization' in api_key_prefix)

    def test_KubernetesApiAuthenticationVariants(self):
        api_key, api_key_prefix, mock_api = self._mock_api()
        mock_logger = MagicMock()
        authentication_data = {'gcp_service_account': {'blah': 'blah'}}

        instance = KubernetesApiAuthenticationVariants(
            mock_logger,
            authentication_data
        )

        def fake_authenticate(tested_instance, api):
            self.assertEquals(mock_api, api)
            self.assertEquals(
                tested_instance.authentication_data,
                authentication_data
            )

            return True

        with patch(
                'cloudify_kubernetes.k8s.authentication.'
                'GCPServiceAccountAuthentication.authenticate',
                fake_authenticate
        ):
            self.assertTrue(instance.authenticate(mock_api))


if __name__ == '__main__':
    unittest.main()
