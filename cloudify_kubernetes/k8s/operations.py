from kubernetes.client.rest import ApiException

from .exceptions import KuberentesApiOperationError


class KubernetesOperartion(object):

    API_ACCEPTED_ARGUMENTS = []

    def __init__(self, api_method, api_method_arguments_names):
        self.api_method = api_method
        self.api_method_arguments_names = api_method_arguments_names

    def _prepare_arguments(self, arguments):
        result_arguments = {}

        for mandatory_argument_name in self.api_method_arguments_names:
            if mandatory_argument_name in arguments:
                result_arguments[mandatory_argument_name] = arguments[mandatory_argument_name]
            else:
                raise KuberentesApiOperationError(
                    'Invalid input data for execution of Kubernetes API method: '
                    'input argument {0} is not defined but is mandatory'
                    .format(mandatory_argument_name))

        for optional_argument_name in self.API_ACCEPTED_ARGUMENTS:
            if optional_argument_name in arguments:
                result_arguments[optional_argument_name] = arguments[optional_argument_name]

        return result_arguments

    def execute(self, arguments):
        try:
            return self.api_method(**self._prepare_arguments(arguments))
        except ApiException as e:
            raise KuberentesApiOperationError(
                'Operation execution failed. Exception during Kubernetes API call: {0}'
                .format(str(e)))


class KubernetesCreateOperation(KubernetesOperartion):
    pass


class KubernetesReadOperation(KubernetesOperartion):

    API_ACCEPTED_ARGUMENTS = ['exact', 'export']


class KubernetesDeleteOperation(KubernetesOperartion):

    API_ACCEPTED_ARGUMENTS = ['grace_period_seconds', 'orphan_dependents']
