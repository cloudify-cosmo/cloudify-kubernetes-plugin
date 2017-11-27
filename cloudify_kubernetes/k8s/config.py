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

import kubernetes
import os
import yaml

from .exceptions import KuberentesApiInitializationFailedError

CONFIG = type.__call__(kubernetes.client.Configuration)


class KubernetesApiConfiguration(object):

    @classmethod
    def get_kube_config_loader(cls, **kwargs):
        return kubernetes.config.kube_config.KubeConfigLoader(
            get_google_credentials=lambda: '',
            **kwargs
        )

    @classmethod
    def get_kube_config_loader_from_file(cls, config_file, **kwargs):
        with open(config_file) as file:
            return cls.get_kube_config_loader(
                config_dict=yaml.load(file),
                config_base_path=os.path.abspath(
                    os.path.dirname(config_file)
                ),
                **kwargs
            )

    def __init__(self, logger, configuration_data, **kwargs):
        self.logger = logger
        self.configuration_data = configuration_data
        self.kwargs = kwargs

    def _do_prepare_api(self):
        return None

    def prepare_api(self):
        api = self._do_prepare_api()

        if not api:
            raise KuberentesApiInitializationFailedError(
                'Cannot initialize Kubernetes API with {0} configuration '
                'and {1} properties'
                .format(self.__class__.__name__, self.configuration_data))

        return api


class BlueprintFileConfiguration(KubernetesApiConfiguration):
    BLUEPRINT_FILE_NAME_KEY = 'blueprint_file_name'

    def _do_prepare_api(self):
        if self.BLUEPRINT_FILE_NAME_KEY in self.configuration_data:
            blueprint_file_name = self.configuration_data[
                self.BLUEPRINT_FILE_NAME_KEY
            ]

            try:
                download_resource = self.kwargs.get('download_resource')
                manager_file_path = download_resource(blueprint_file_name)

                if manager_file_path and os.path.isfile(
                    os.path.expanduser(manager_file_path)
                ):
                    self.get_kube_config_loader_from_file(
                        config_file=manager_file_path
                    ).load_and_set(CONFIG)

                    return kubernetes.client
            except Exception as e:
                self.logger.error(
                    'Cannot download config file from blueprint: {0}'
                    .format(str(e))
                )

        return None


class ManagerFilePathConfiguration(KubernetesApiConfiguration):
    MANAGER_FILE_PATH_KEY = 'manager_file_path'

    def _do_prepare_api(self):
        if self.MANAGER_FILE_PATH_KEY in self.configuration_data:
            manager_file_path = self.configuration_data[
                self.MANAGER_FILE_PATH_KEY
            ]

            if manager_file_path and os.path.isfile(
                os.path.expanduser(manager_file_path)
            ):
                self.get_kube_config_loader_from_file(
                    config_file=manager_file_path
                ).load_and_set(CONFIG)

                return kubernetes.client

        return None


class FileContentConfiguration(KubernetesApiConfiguration):
    FILE_CONTENT_KEY = 'file_content'

    def _do_prepare_api(self):

        if self.FILE_CONTENT_KEY in self.configuration_data:
            file_content = self.configuration_data[self.FILE_CONTENT_KEY]

            self.get_kube_config_loader(config_dict=file_content)\
                .load_and_set(CONFIG)

            return kubernetes.client

        return None


class ApiOptionsConfiguration(KubernetesApiConfiguration):
    API_OPTIONS_KEY = 'api_options'
    API_OPTIONS_HOST_KEY = 'host'
    API_OPTIONS_ALL_KEYS = ['host', 'ssl_ca_cert', 'cert_file', 'key_file',
                            'verify_ssl']

    def _do_prepare_api(self):
        if self.API_OPTIONS_KEY in self.configuration_data:
            api_options = self.configuration_data[self.API_OPTIONS_KEY]

            if self.API_OPTIONS_HOST_KEY not in api_options:
                return None

            api = kubernetes.client
            for key in self.API_OPTIONS_ALL_KEYS:
                if key in api_options:
                    setattr(api.configuration, key, api_options[key])

            return api
        return None


class KubernetesApiConfigurationVariants(KubernetesApiConfiguration):

    VARIANTS = (
        BlueprintFileConfiguration,
        ManagerFilePathConfiguration,
        FileContentConfiguration,
        ApiOptionsConfiguration
    )

    def _do_prepare_api(self):
        self.logger.debug(
            'Checking how Kubernetes API should be configured'
        )

        for variant in self.VARIANTS:
            try:
                api_candidate = variant(
                    self.logger,
                    self.configuration_data,
                    **self.kwargs
                ).prepare_api()

                self.logger.debug(
                    'Configuration option {0} will be used'
                    .format(variant.__name__)
                )

                return api_candidate
            except KuberentesApiInitializationFailedError:
                self.logger.debug(
                    'Configuration option {0} cannot be used'
                    .format(variant.__name__)
                )

        raise KuberentesApiInitializationFailedError(
            'Cannot initialize Kubernetes API - no suitable configuration '
            'variant found for {0} properties'
            .format(self.configuration_data)
        )
