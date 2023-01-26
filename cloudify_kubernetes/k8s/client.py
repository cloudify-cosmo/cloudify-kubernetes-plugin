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

import kubernetes

from cloudify.exceptions import NonRecoverableError

from .._compat import text_type, getfullargspec
from .operations import (KubernetesReadOperation,
                         KubernetesDeleteOperation,
                         KubernetesUpdateOperation,
                         KubernetesCreateOperation)
from .exceptions import (KuberentesApiOperationError,
                         KuberentesInvalidApiClassError,
                         KuberentesInvalidApiMethodError,
                         KuberentesInvalidPayloadClassError,
                         KuberentesInvalidDefinitionError
                         )

API_VERSION_DEFINITION = "apiVersion"
METADATA_DEFINITION = "metadata"
KIND_DEFINITION = "kind"


class KubernetesResourceDefinition(object):

    def __init__(self,
                 kind=None,
                 apiVersion=None,
                 metadata=None,
                 spec=None,
                 parameters=None,
                 provisioner=None,
                 data=None,
                 roleRef=None,
                 subjects=None,
                 automountServiceAccountToken=False,
                 imagePullSecrets=None,
                 secrets=None,
                 type=None,
                 stringData=None,
                 rules=None,
                 **unexposed_keys):

        if kind is None or apiVersion is None or metadata is None:
            raise KuberentesInvalidDefinitionError(
                'Incorrect format of resource definition,one or more '
                'of: {0}, '
                '{1}, {2} '
                'are missing.'.format(
                    API_VERSION_DEFINITION, METADATA_DEFINITION,
                    KIND_DEFINITION))

        self.kind = kind.split('.')[-1]
        self.api_version = apiVersion
        self.metadata = metadata

        # General classes
        if spec:
            self.spec = spec
        # Storage class
        if parameters:
            self.parameters = parameters
        if provisioner:
            self.provisioner = provisioner
        # Config class  | Secret
        if data:
            self.data = data
        # roleRef
        if roleRef:
            self.role_ref = roleRef
        # subjects
        if subjects:
            self.subjects = subjects
        # automountServiceAccountToken
        if automountServiceAccountToken:
            self.automount_service_account_token = automountServiceAccountToken
        # imagePullSecrets
        if imagePullSecrets:
            self.image_pull_secrets = imagePullSecrets
        # secrets
        if secrets:
            self.secrets = secrets
        # type
        if type:
            self.type = type
        # stringData
        if stringData:
            self.string_data = stringData
        # rules
        if rules:
            self.rules = rules
        for key, value in unexposed_keys.items():
            setattr(self, key, value)

    @staticmethod
    def underscore_to_camelcase(value):
        def camelcase():
            yield str.lower
            while True:
                yield str.capitalize

        c = camelcase()
        return "".join(next(c)(x) if x else '_' for x in value.split("_"))

    def to_dict(self):
        return dict(
            (self.underscore_to_camelcase(key), value) for (key, value)
            in self.__dict__.items() if key != 'underscore_to_camelcase')


class CloudifyKubernetesClient(object):

    def __init__(self,
                 logger,
                 api_configuration=None,
                 api_authentication=None,
                 api_client=None):

        self.logger = logger
        self.client = api_client
        self.api = kubernetes.client

        if not self.client:
            self.logger.debug(
                'Deprecated client initialization. Please contact support.')
            self.configuration = None
            prepare_api = api_configuration.prepare_api()
            if isinstance(prepare_api, kubernetes.client.Configuration):

                if api_authentication:
                    self.configuration = api_authentication.authenticate(
                        prepare_api)
                else:
                    self.configuration = prepare_api

                self.api.configuration = \
                    kubernetes.client.Configuration.set_default(
                        self.configuration)
                self.client = kubernetes.client.ApiClient(
                    configuration=self.api.configuration)

            else:

                if prepare_api:
                    self.api = prepare_api

                self.client = self.api.ApiClient()

        self.logger.debug('Kubernetes API initialized successfully.')

    @property
    def _name(self):
        return self.api.__class__.__name__

    def _prepare_payload(self, class_name, resource_definition):
        if class_name is None:
            return resource_definition.to_dict()
        if not hasattr(self.api, class_name):
            raise KuberentesInvalidPayloadClassError(
                'Cannot create instance of Kubernetes API payload class: {0}. '
                'Class not supported by client {1}'
                .format(class_name, self._name))
        self.logger.debug('Kubernetes API initialized successfully')
        return getattr(self.api, class_name)(**vars(resource_definition))

    def _prepare_api_method(self, class_name, method_name):
        if hasattr(self.api, class_name):
            api = getattr(self.api, class_name)(api_client=self.client)

            if hasattr(api, method_name):
                method = getattr(api, method_name)
                return method, [
                    arg for arg in getfullargspec(method).args
                    if not arg == 'self'
                ]

            raise KuberentesInvalidApiMethodError(
                'Method {0} not supported by Kubernetes API class {1}'
                .format(method_name, class_name))

        raise KuberentesInvalidApiClassError(
            'Cannot create instance of Kubernetes API class: {0}. Class not '
            'supported by client {1}'
            .format(class_name, self._name))

    def _prepare_operation(self, operation, api, method, **_):
        api_method, api_method_arguments_names = self._prepare_api_method(
            api, method
        )
        self.logger.debug('Preparing operation with api method: {0} '
                          '(mandatory arguments: {1})'
                          .format(api_method, api_method_arguments_names))

        return operation(api_method, api_method_arguments_names)

    def _prepare_delete_options_resource(self, class_name,
                                         resource_definition, options):
        if resource_definition.kind != 'ReplicationController':
            if options:
                if hasattr(self.api, class_name):
                    node_options = \
                        {k: v for k, v in options.items()
                         if hasattr(getattr(self.api, class_name), k)}

                    return getattr(self.api, class_name)(**node_options)

            # This is the default should be provided even if the user does not
            # provide the ``propagation_policy`` as part of the option
            return getattr(self.api, class_name)(
                **{'propagation_policy': 'Foreground'})

        return None

    def _execute(self, operation, arguments):
        for k, v in list(arguments.items()):
            if not v:
                del arguments[k]
        try:
            self.logger.debug('Executing operation {0}'.format(operation))
            self.logger.debug('Executing operation arguments {0}'.format(
                arguments))
            result = operation.execute(arguments)
            self.logger.debug('Operation executed successfully')
            self.logger.debug('Result: {0}'.format(result))

            return result
        except kubernetes.client.rest.ApiException as e:
            if 'the namespace of the provided object does not match ' \
               'the namespace sent on the request' in text_type(e):
                raise NonRecoverableError(text_type(e))
            raise KuberentesApiOperationError(
                'Exception during Kubernetes API call: {0}'.format(
                    text_type(e))
            )

    def match_namespace(self, resource_definition, options):
        namespace_from_def = resource_definition.metadata.get('namespace')
        if namespace_from_def and 'namespace' in options:
            if options['namespace'] != namespace_from_def:
                self.logger.error(
                    'Namespace from metadata does not match namespace in '
                    'request - using the namespace from the metadata.')
                options['namespace'] = namespace_from_def
        self.logger.debug('Options API Request {0}'.format(options))

    def execute_with_alternates(self,
                                operation, mapping, options, mapping_key):
        api_and_method = getattr(mapping, mapping_key)
        try:
            return self._execute(self._prepare_operation(
                operation, **vars(api_and_method)), options)
        except KuberentesApiOperationError as e:
            str_e = str(e)
            if 'does not match the expected API version' in str_e:
                self.logger.error(
                    'The mapping API and Method {} failed: {}'.format(
                        api_and_method, str_e))
                for alternate in api_and_method.alternates:
                    try:
                        return self._execute(self._prepare_operation(
                            operation, **vars(alternate)), options)
                    except KuberentesApiOperationError as e2:
                        str_e2 = str(e2)
                        if 'does not match the expected API version' not in \
                                str_e2:
                            raise e2
                        self.logger.error(
                            'The alternate mapping API and Method '
                            '{} {} failed: {}'.format(
                                alternate.api, alternate.payload, str(e2)))
                        continue
            raise e

    def create_resource(self, mapping, resource_definition, options):
        options['body'] = self._prepare_payload(
            mapping.create.payload, resource_definition
        )
        self.match_namespace(resource_definition, options)
        self.logger.debug('Options API Request {0}'.format(options))
        return self.execute_with_alternates(
            KubernetesCreateOperation, mapping, options, 'create')

    def read_resource(self, mapping, resource_definition, options):
        options['name'] = resource_definition.metadata['name']
        self.match_namespace(resource_definition, options)

        return self.execute_with_alternates(
            KubernetesReadOperation, mapping, options, 'read')

    def update_resource(self, mapping, resource_definition, options):
        options['body'] = self._prepare_payload(
            mapping.create.payload, resource_definition
        )
        options['name'] = resource_definition.metadata['name']
        self.match_namespace(resource_definition, options)
        return self.execute_with_alternates(
            KubernetesUpdateOperation, mapping, options, 'update')

    def delete_resource(self, mapping, resource_definition,
                        resource_id, options):

        if resource_definition.kind != 'ReplicationController':

            # Set name of resource
            options['name'] = resource_id

            # Generate body object with available options
            delete_resource = \
                self._prepare_delete_options_resource(mapping.delete.payload,
                                                      resource_definition,
                                                      options)
            options['body'] = delete_resource

            # Check if body exists that mean the type is ``V1DeleteOptions``
            #  and the options for ``V1DeleteOptions`` is already on the body

            # Trim '_' from ``delete_resource`` instance keys
            # Since these represent options args
            if isinstance(delete_resource, kubernetes.client.V1DeleteOptions):
                delete_resource = \
                    {k[1:]: v for k, v in vars(delete_resource).items()}

            # Pass options that did not include on the ``delete_resource``
            options = {k: v for k, v in options.items()
                       if k not in delete_resource.keys()}

        self.match_namespace(resource_definition, options)
        return self.execute_with_alternates(
            KubernetesDeleteOperation, mapping, options, 'delete')
