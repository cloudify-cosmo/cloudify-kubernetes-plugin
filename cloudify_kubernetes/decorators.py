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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import sys
from cloudify.exceptions import (
    OperationRetry,
    RecoverableError,
    NonRecoverableError
)
from cloudify.utils import exception_to_error_cause
from cloudify.workflows.workflow_context import CloudifyWorkflowContext
from cloudify.manager import (
    download_resource as manager_download_resource,
    get_rest_client)
from .utils import get_ctx_from_kwargs
from .k8s import (CloudifyKubernetesClient,
                  KubernetesApiAuthenticationVariants,
                  KubernetesApiConfigurationVariants,
                  KuberentesApiInitializationFailedError,
                  KuberentesInvalidPayloadClassError,
                  KuberentesInvalidApiClassError,
                  KuberentesInvalidApiMethodError,
                  KuberentesMappingNotFoundError)


NODE_PROPERTY_AUTHENTICATION = 'authentication'
NODE_PROPERTY_CONFIGURATION = 'configuration'
RELATIONSHIP_TYPE_MANAGED_BY_MASTER = (
    'cloudify.kubernetes.relationships.managed_by_master'
)


class pseudo_node_instance(object):
    # The workflow context is an abomination.
    pass


def build_node_instance(node_instance_id):
    cfy_rest_client = get_rest_client()
    node_instance_response = \
        cfy_rest_client.node_instances.get(
            node_instance_id,
            evaluate_functions=True)
    node_response = cfy_rest_client.nodes.get(
        node_instance_response.deployment_id,
        node_instance_response.node_id,
        evaluate_functions=True)
    node_instance = pseudo_node_instance()
    setattr(node_instance, 'node_instance', node_instance_response)
    setattr(node_instance, 'node', node_response)
    return node_instance


def _retrieve_master(resource_instance):
    if isinstance(resource_instance, pseudo_node_instance):
        for relationship in \
                resource_instance.node_instance.get('relationships', []):
            if relationship.get('type', '') == \
                    RELATIONSHIP_TYPE_MANAGED_BY_MASTER:
                return build_node_instance(relationship.get('target_id', ''))
    else:
        for relationship in resource_instance.relationships:
            rel_type = relationship.type
            if rel_type == RELATIONSHIP_TYPE_MANAGED_BY_MASTER:
                return relationship.target
    raise NonRecoverableError(
        'No relationship to a cloudify.kubernetes.nodes.Master was provided.')


def _retrieve_property(resource_instance,
                       property_name):
    master = _retrieve_master(resource_instance)
    if isinstance(master, pseudo_node_instance):
        configuration = master.node.get(
            'properties', {}).get(
            property_name, {})
        configuration.update(
            master.node_instance.get(
                'runtime_properties', {}).get(
                property_name, {})
        )
        return configuration
    configuration = master.node.properties.get(property_name, {})
    configuration.update(
        master.instance.runtime_properties.get(property_name, {})
    )
    return configuration


def resource_task(retrieve_resource_definition, retrieve_mapping):
    def decorator(task, **kwargs):
        def wrapper(**kwargs):
            try:
                kwargs['resource_definition'] = \
                    retrieve_resource_definition(**kwargs)
                kwargs['api_mapping'] = retrieve_mapping(**kwargs)
                task(**kwargs)
            except (KuberentesMappingNotFoundError,
                    KuberentesInvalidPayloadClassError,
                    KuberentesInvalidApiClassError,
                    KuberentesInvalidApiMethodError) as e:
                raise NonRecoverableError(str(e))
            except OperationRetry as e:
                _, exc_value, exc_traceback = sys.exc_info()
                raise OperationRetry(
                    '{0}'.format(str(e)),
                    retry_after=15,
                    causes=[exception_to_error_cause(exc_value, exc_traceback)]
                )
            except NonRecoverableError as e:
                _, exc_value, exc_traceback = sys.exc_info()
                raise NonRecoverableError(
                    '{0}'.format(str(e)),
                    causes=[exception_to_error_cause(exc_value, exc_traceback)]
                )
            except Exception as e:
                _, exc_value, exc_traceback = sys.exc_info()
                raise RecoverableError(
                    '{0}'.format(str(e)),
                    causes=[exception_to_error_cause(exc_value, exc_traceback)]
                )
        return wrapper
    return decorator


def with_kubernetes_client(function):
    def wrapper(**kwargs):

        _ctx, node_instance = get_ctx_from_kwargs(kwargs)

        if isinstance(_ctx, CloudifyWorkflowContext):
            node_instance = build_node_instance(node_instance.id)

        configuration_property = _retrieve_property(
            node_instance,
            NODE_PROPERTY_CONFIGURATION
        )

        authentication_property = _retrieve_property(
            node_instance,
            NODE_PROPERTY_AUTHENTICATION
        )

        try:
            _download_resource = _ctx.download_resource
        except AttributeError:
            _download_resource = manager_download_resource

        try:
            kwargs['client'] = CloudifyKubernetesClient(
                _ctx.logger,
                KubernetesApiConfigurationVariants(
                    _ctx.logger,
                    configuration_property,
                    download_resource=_download_resource
                ),
                KubernetesApiAuthenticationVariants(
                    _ctx.logger,
                    authentication_property
                )
            )

            function(**kwargs)
        except KuberentesApiInitializationFailedError as e:
            _, exc_value, exc_traceback = sys.exc_info()
            raise RecoverableError(
                '{0}'.format(str(e)),
                causes=[exception_to_error_cause(exc_value, exc_traceback)]
            )

    return wrapper
