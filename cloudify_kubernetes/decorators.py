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
#

from cloudify import ctx
from cloudify.exceptions import RecoverableError, NonRecoverableError

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


def _retrieve_master(resource_instance):
    for relationship in resource_instance.relationships:
        if relationship.type == RELATIONSHIP_TYPE_MANAGED_BY_MASTER:
            return relationship.target


def _retrieve_property(resource_instance, property_name):
    target = _retrieve_master(resource_instance)
    configuration = target.node.properties.get(property_name, {})
    configuration.update(
        target.instance.runtime_properties.get(property_name, {})
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
            except Exception as e:
                raise RecoverableError(str(e))

        return wrapper
    return decorator


def with_kubernetes_client(function):
    def wrapper(**kwargs):
        configuration_property = _retrieve_property(
            ctx.instance,
            NODE_PROPERTY_CONFIGURATION
        )

        authentication_property = _retrieve_property(
            ctx.instance,
            NODE_PROPERTY_AUTHENTICATION
        )

        try:
            kwargs['client'] = CloudifyKubernetesClient(
                ctx.logger,
                KubernetesApiConfigurationVariants(
                    ctx.logger,
                    configuration_property,
                    download_resource=ctx.download_resource
                ),
                KubernetesApiAuthenticationVariants(
                    ctx.logger,
                    authentication_property
                )
            )

            function(**kwargs)
        except KuberentesApiInitializationFailedError as e:
            raise RecoverableError(e)

    return wrapper
