import inspect
from kubernetes.client.rest import ApiException

from .exceptions import *
from .operations import *


class CloudifyKubernetesClient(object):

    def __init__(self, api_configuration, logger):
        self.logger = logger
        self.api = api_configuration.prepare_api()
        self.logger.info('Kubernetes API initialized successfully')

    @property
    def _name(self):
        return self.api.__class__.__name__

    def _prepare_payload(self, class_name, resource_definition):
        if hasattr(self.api, class_name):
            return getattr(self.api, class_name)(**vars(resource_definition))

        raise KuberentesInvalidPayloadClassError(
            'Cannot create instance of Kubernetes API payload class: {0}. Class not supported by client {1}'
            .format(class_name, self._name))

    def _prepare_api_method(self, class_name, method_name):
        if hasattr(self.api, class_name):
            api = getattr(self.api, class_name)()

            if hasattr(api, method_name):
                method = getattr(api, method_name)
                return method, [arg for arg in inspect.getargspec(method).args if not arg == 'self']

            raise KuberentesInvalidApiMethodError(
                'Method {0} not supported by Kubernetes API class {1}'
                .format(method_name, class_name))

        raise KuberentesInvalidApiClassError(
            'Cannot create instance of Kubernetes API class: {0}. Class not supported by client {1}'
            .format(class_name, self._name))

    def _prepare_operation(self, operation, api, method, **kwargs):
        api_method, api_method_arguments_names = self._prepare_api_method(api, method)
        self.logger.info('Prepering operation with api method: {0} (mandatory arguments: {1})'
                         .format(api_method, api_method_arguments_names))

        return operation(api_method, api_method_arguments_names)

    def _execute(self, operation, arguments):
        try:
            self.logger.info('Executing operation {0}'.format(operation))

            result = operation.execute(arguments)
            self.logger.info('Operation executed successfully')
            self.logger.debug('Result: {0}'.format(result))

            return result
        except ApiException as e:
            raise KuberentesApiOperationError('Exception during Kubernetes API call: {0}'.format(str(e)))

    def create_resource(self, mapping, resource_definition, options):
        options['body'] = self._prepare_payload(mapping.create['payload'], resource_definition)
        return self._execute(self._prepare_operation(KubernetesCreateOperation, **mapping.create), options)

    def read_resource(self, mapping, resource_id, options):
        options['name'] = resource_id
        return self._execute(self._prepare_operation(KubernetesReadOperation, **mapping.read), options)

    def delete_resource(self, mapping, resource_id, options):
        options['name'] = resource_id
        options['body'] = {}
        return self._execute(self._prepare_operation(KubernetesDeleteOperation, **mapping.delete), options)

