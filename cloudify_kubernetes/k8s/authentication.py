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

import json

from oauth2client.service_account import ServiceAccountCredentials

from .._compat import text_type
from .exceptions import KuberentesAuthenticationError


class KubernetesApiAuthentication(object):

    def __init__(self, logger, authentication_data):
        self.logger = logger
        self.authentication_data = authentication_data

    def _do_authenticate(self, api):
        if api:
            return api

    def authenticate(self, api):
        authenticated = self._do_authenticate(api)
        if authenticated:
            return authenticated

        raise KuberentesAuthenticationError(
            'Cannot use {0} authenticate option for data: {1} and API: {2}'
            .format(
                self.__class__.__name__,
                self.authentication_data,
                api
            )
        )


class StandardBearerToken(KubernetesApiAuthentication):

    def _do_authenticate(self, api):

        if hasattr(api, 'api_key') and hasattr(api, 'api_key_prefix'):
            return api

        raise KuberentesAuthenticationError(
            'Cannot use {0} authenticate option for data: {1} and API: {2}'
            .format(
                self.__class__.__name__,
                self.authentication_data,
                api
            )
        )


class GCPServiceAccountAuthentication(KubernetesApiAuthentication):

    K8S_API_AUTHORIZATION = 'authorization'

    ENV_CREDENTIALS = 'GOOGLE_APPLICATION_CREDENTIALS'

    PROPERTY_GCE_SERVICE_ACCOUNT = 'gcp_service_account'

    SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

    TOKEN_PREFIX = 'Bearer'

    def _do_authenticate(self, configuration):
        service_account_file_content = self.authentication_data.get(
            self.PROPERTY_GCE_SERVICE_ACCOUNT
        )
        if service_account_file_content:

            if isinstance(service_account_file_content, text_type):
                service_account_file_content = \
                    json.loads(service_account_file_content)

            credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                service_account_file_content,
                self.SCOPES
            )
            token = credentials.get_access_token().access_token
            configuration.api_key[self.K8S_API_AUTHORIZATION] = token
            configuration.api_key_prefix[self.K8S_API_AUTHORIZATION]\
                = self.TOKEN_PREFIX
            return configuration

        raise KuberentesAuthenticationError(
            'Cannot use {0} authenticate option for data: {1} and API: {2}'
            .format(
                self.__class__.__name__,
                self.authentication_data,
                configuration
            )
        )


class KubernetesApiAuthenticationVariants(KubernetesApiAuthentication):

    VARIANTS = (
        GCPServiceAccountAuthentication,
        StandardBearerToken,
    )

    def authenticate(self, api):
        self.logger.debug('Checking Kubernetes authentication options')

        for variant in self.VARIANTS:
            try:
                candidate = variant(self.logger, self.authentication_data)\
                    .authenticate(api)

                self.logger.debug(
                    'Authentication option {0} will be used'
                    .format(variant.__name__)
                )
                return candidate
            except KuberentesAuthenticationError:
                self.logger.debug(
                    'Authentication option {0} cannot be used'
                    .format(variant.__name__)
                )

        self.logger.warn(
            'Cannot initialize Kubernetes API - no suitable authentication '
            'variant found for {0} properties'
            .format(self.authentication_data)
        )
        return None
