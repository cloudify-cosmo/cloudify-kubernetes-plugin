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
import os
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
        instance = KubernetesApiConfiguration('logger', 'conf')

        self.assertEqual(instance.logger, 'logger')
        self.assertEqual(instance.configuration_data, 'conf')
        self.assertEqual(instance._do_prepare_api(), None)

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()


class TestBlueprintFileConfiguration(unittest.TestCase):

    def test_BlueprintFileConfiguration_Error(self):
        mock_download_resource = MagicMock(side_effect=Exception())
        mock_logger = MagicMock()

        instance = BlueprintFileConfiguration(
            mock_logger,
            {'blueprint_file_name': 'kubernetes.conf'},
            download_resource=mock_download_resource
        )

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

        mock_download_resource.assert_called_with('kubernetes.conf')

    def test_BlueprintFileConfiguration(self):
        mock_download_resource = MagicMock()
        mock_logger = MagicMock()
        mock_client = MagicMock()
        mock_loader = MagicMock()
        mock_kubernetes_config_load_kube_config = MagicMock(
            return_value=mock_loader
        )
        mock_download_resource = MagicMock(
            return_value="downloaded_resource"
        )

        instance = BlueprintFileConfiguration(
            mock_logger,
            {'blueprint_file_name': 'kubernetes.conf'},
            download_resource=mock_download_resource
        )

        mock_isfile = MagicMock(return_value=True)

        with patch('os.path.isfile', mock_isfile):
            with patch(
                    'cloudify_kubernetes.k8s.config.'
                    'kubernetes.config.load_kube_config',
                    mock_kubernetes_config_load_kube_config
            ):
                with patch('kubernetes.client', mock_client):
                    self.assertEqual(
                        instance.prepare_api(), mock_client
                    )

        mock_download_resource.assert_called_with('kubernetes.conf')
        mock_kubernetes_config_load_kube_config.assert_called_with(
            config_file='downloaded_resource'
        )


class TestManagerFilePathConfiguration(unittest.TestCase):

    def test_ManagerFilePathConfiguration_Error(self):
        mock_logger = MagicMock()

        instance = ManagerFilePathConfiguration(
            mock_logger,
            {'manager_file_path': 'kubernetes.conf'}
        )

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

    def test_ManagerFilePathConfiguration(self):
        mock_logger = MagicMock()
        mock_client = MagicMock()
        mock_loader = MagicMock()
        mock_kubernetes_config_load_kube_config = MagicMock(
            return_value=mock_loader
        )

        instance = ManagerFilePathConfiguration(mock_logger, {
            'manager_file_path': 'kubernetes.conf'
        })

        mock_isfile = MagicMock(return_value=True)

        with patch('os.path.isfile', mock_isfile):
            with patch(
                    'cloudify_kubernetes.k8s.config.'
                    'kubernetes.config.load_kube_config',
                    mock_kubernetes_config_load_kube_config
            ):
                with patch('kubernetes.client', mock_client):
                    self.assertEqual(
                        instance.prepare_api(), mock_client
                    )

        mock_isfile.assert_called_with('kubernetes.conf')
        mock_kubernetes_config_load_kube_config.assert_called_with(
            config_file='kubernetes.conf'
        )


class TestFileContentConfiguration(unittest.TestCase):

    def test_FileContentConfiguration_Error(self):
        mock_logger = MagicMock()
        download_resource_mock = MagicMock(side_effect=Exception())

        instance = FileContentConfiguration(
            mock_logger,
            {},
            download_resource=download_resource_mock
        )

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

    def test_FileContentConfiguration(self):
        mock_download_resource = MagicMock()
        mock_logger = MagicMock()
        mock_config = MagicMock()
        mock_client = MagicMock()

        instance = FileContentConfiguration(
            mock_logger,
            {'file_content': 'kubernetes.conf'},
            download_resource=mock_download_resource
        )

        with patch(
            'kubernetes.config.kube_config.KubeConfigLoader', mock_config
        ):
            with patch('kubernetes.client', mock_client):
                self.assertEqual(
                    instance.prepare_api(), mock_client
                )

        mock_config.assert_called_with(
            config_dict='kubernetes.conf',
            config_base_path=os.path.expanduser('~/.kube')
        )


class TestApiOptionsConfiguration(unittest.TestCase):

    def test_ApiOptionsConfiguration_Error(self):
        mock_logger = MagicMock()

        instance = ApiOptionsConfiguration(mock_logger, {})

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

    def test_ApiOptionsConfiguration_EmptyError(self):
        mock_logger = MagicMock()

        instance = ApiOptionsConfiguration(mock_logger, {
            'api_options': {}
        })

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

    def test_ApiOptionsConfiguration(self):
        mock_logger = MagicMock()
        mock_client = MagicMock()

        instance = ApiOptionsConfiguration(mock_logger, {
            'api_options': {'host': 'some_host'}
        })

        with patch('kubernetes.client', mock_client):
            self.assertEqual(
                instance.prepare_api(), mock_client
            )

        # check keys
        instance = ApiOptionsConfiguration(mock_logger, {
            'api_options': {'host': 'some_host',
                            'api_key': 'secret key'}
        })

        with patch('kubernetes.client', mock_client):
            config = MagicMock()
            mock_client.Configuration = MagicMock(return_value=config)
            self.assertEqual(
                instance.prepare_api(), mock_client
            )
            self.assertEqual(config.api_key,
                             {'authorization': 'Bearer secret key'})


class TestKubernetesApiConfigurationVariants(unittest.TestCase):

    def test_KubernetesApiConfigurationVariants_Error(self):
        mock_download_resource = MagicMock(side_effect=Exception())
        mock_logger = MagicMock()

        instance = KubernetesApiConfigurationVariants(
            mock_logger,
            {},
            download_resource=mock_download_resource
        )

        with self.assertRaises(KuberentesApiInitializationFailedError):
            instance.prepare_api()

    def test_KubernetesApiConfigurationVariants(self):
        mock_logger = MagicMock()
        mock_config = MagicMock()
        mock_client = MagicMock()

        instance = KubernetesApiConfigurationVariants(
            mock_logger,
            {'file_content': 'kubernetes.conf'}
        )

        with patch(
            'kubernetes.config.kube_config.KubeConfigLoader', mock_config
        ):
            with patch('kubernetes.client', mock_client):
                self.assertEqual(
                    instance.prepare_api(), mock_client
                )

        mock_config.assert_called_with(
            config_dict='kubernetes.conf',
            config_base_path=os.path.expanduser('~/.kube')
        )


if __name__ == '__main__':
    unittest.main()
