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

from cloudify_kubernetes.k8s.config import (KubernetesApiConfigurationVariants,
                                            ManagerFilePathConfiguration,
                                            BlueprintFileConfiguration,
                                            KubernetesApiConfiguration,
                                            FileContentConfiguration,
                                            ApiOptionsConfiguration)
from cloudify_kubernetes.k8s.exceptions import (
    KuberentesApiInitializationFailedError
)


class TestKubernetesApiConfiguration(unittest.TestCase):

    def test_KubernetesApiConfiguration(self):
        instance = KubernetesApiConfiguration('ctx', 'conf')

        self.assertEqual(instance.ctx, 'ctx')
        self.assertEqual(instance.configuration_data, 'conf')
        self.assertEqual(instance._do_prepare_api(), None)

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()


class TestBlueprintFileConfiguration(unittest.TestCase):

    def test_BlueprintFileConfiguration_Error(self):
        ctx_mock = MagicMock()

        ctx_mock.download_resource = MagicMock(side_effect=Exception())

        instance = BlueprintFileConfiguration(ctx_mock, {
            'blueprint_file_name': 'kubernetes.conf'
        })

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

        ctx_mock.download_resource.assert_called_with('kubernetes.conf')

    def test_BlueprintFileConfiguration(self):
        ctx_mock = MagicMock()
        mock_config = MagicMock()
        mock_client = MagicMock()

        ctx_mock.download_resource = MagicMock(
            return_value="downloaded_resource"
        )

        instance = BlueprintFileConfiguration(ctx_mock, {
            'blueprint_file_name': 'kubernetes.conf'
        })

        mock_isfile = MagicMock(return_value=True)

        with patch('os.path.isfile', mock_isfile):
            with patch('kubernetes.config.load_kube_config', mock_config):
                with patch('kubernetes.client', mock_client):
                    self.assertEqual(
                        instance.prepare_api(), mock_client
                    )

        ctx_mock.download_resource.assert_called_with('kubernetes.conf')
        mock_config.assert_called_with(config_file='downloaded_resource')


class TestManagerFilePathConfiguration(unittest.TestCase):

    def test_ManagerFilePathConfiguration_Error(self):
        ctx_mock = MagicMock()

        ctx_mock.download_resource = MagicMock(side_effect=Exception())

        instance = ManagerFilePathConfiguration(ctx_mock, {
            'manager_file_path': 'kubernetes.conf'
        })

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

    def test_ManagerFilePathConfiguration(self):
        ctx_mock = MagicMock()
        mock_config = MagicMock()
        mock_client = MagicMock()

        instance = ManagerFilePathConfiguration(ctx_mock, {
            'manager_file_path': 'kubernetes.conf'
        })

        mock_isfile = MagicMock(return_value=True)

        with patch('os.path.isfile', mock_isfile):
            with patch('kubernetes.config.load_kube_config', mock_config):
                with patch('kubernetes.client', mock_client):
                    self.assertEqual(
                        instance.prepare_api(), mock_client
                    )

        mock_isfile.assert_called_with('kubernetes.conf')
        mock_config.assert_called_with(config_file='kubernetes.conf')


class TestFileContentConfiguration(unittest.TestCase):

    def test_FileContentConfiguration_Error(self):
        ctx_mock = MagicMock()

        ctx_mock.download_resource = MagicMock(side_effect=Exception())

        instance = FileContentConfiguration(ctx_mock, {})

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

    def test_FileContentConfiguration(self):
        ctx_mock = MagicMock()
        mock_config = MagicMock()
        mock_client = MagicMock()

        instance = FileContentConfiguration(ctx_mock, {
            'file_content': 'kubernetes.conf'
        })

        with patch(
            'kubernetes.config.kube_config.KubeConfigLoader', mock_config
        ):
            with patch('kubernetes.client', mock_client):
                self.assertEqual(
                    instance.prepare_api(), mock_client
                )

        mock_config.assert_called_with(config_dict='kubernetes.conf')


class TestApiOptionsConfiguration(unittest.TestCase):

    def test_ApiOptionsConfiguration_Error(self):
        ctx_mock = MagicMock()

        instance = ApiOptionsConfiguration(ctx_mock, {})

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

    def test_ApiOptionsConfiguration_EmptyError(self):
        ctx_mock = MagicMock()

        instance = ApiOptionsConfiguration(ctx_mock, {
            'api_options': {}
        })

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

    def test_ApiOptionsConfiguration(self):
        ctx_mock = MagicMock()
        mock_client = MagicMock()

        instance = ApiOptionsConfiguration(ctx_mock, {
            'api_options': {'host': 'some_host'}
        })

        with patch('kubernetes.client', mock_client):
            self.assertEqual(
                instance.prepare_api(), mock_client
            )

        self.assertEqual(mock_client.configuration.host, 'some_host')


class TestKubernetesApiConfigurationVariants(unittest.TestCase):

    def test_KubernetesApiConfigurationVariants_Error(self):
        ctx_mock = MagicMock()

        ctx_mock.download_resource = MagicMock(side_effect=Exception())

        instance = KubernetesApiConfigurationVariants(ctx_mock, {})

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

    def test_KubernetesApiConfigurationVariants(self):
        ctx_mock = MagicMock()
        mock_config = MagicMock()
        mock_client = MagicMock()

        instance = KubernetesApiConfigurationVariants(ctx_mock, {
            'file_content': 'kubernetes.conf'
        })

        with patch(
            'kubernetes.config.kube_config.KubeConfigLoader', mock_config
        ):
            with patch('kubernetes.client', mock_client):
                self.assertEqual(
                    instance.prepare_api(), mock_client
                )

        mock_config.assert_called_with(config_dict='kubernetes.conf')


if __name__ == '__main__':
    unittest.main()
