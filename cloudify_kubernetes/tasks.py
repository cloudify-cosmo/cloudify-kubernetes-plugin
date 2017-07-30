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

import yaml

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import RecoverableError, NonRecoverableError

from .k8s import (CloudifyKubernetesClient,
                  KubernetesApiAuthenticationVariants,
                  KubernetesApiConfigurationVariants,
                  KuberentesApiInitializationFailedError,
                  KubernetesApiMapping,
                  KubernetesResourceDefinition,
                  KuberentesInvalidPayloadClassError,
                  KuberentesInvalidApiClassError,
                  KuberentesInvalidApiMethodError)


INSTANCE_RUNTIME_PROPERTY_KUBERNETES = 'kubernetes'
NODE_PROPERTY_API_MAPPING = '_api_mapping'
NODE_PROPERTY_AUTHENTICATION = 'authentication'
NODE_PROPERTY_CONFIGURATION = 'configuration'
NODE_PROPERTY_DEFINITION = 'definition'
NODE_PROPERTY_OPTIONS = 'options'
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


def retrieve_id(resource_instance):
    return resource_instance.runtime_properties[
        INSTANCE_RUNTIME_PROPERTY_KUBERNETES
    ]['metadata']['name']


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


def _yaml_from_file(
        resource_path,
        target_path,
        template_variables):

    downloaded_file_path = \
        ctx.download_resource_and_render(
            resource_path,
            target_path,
            template_variables)

    with open(downloaded_file_path) as outfile:
        file_content = outfile.read()

    return yaml.load(file_content)


def resource_task(task, **kwargs):
    def wrapper(**kwargs):

        node_property_definition = \
            ctx.node.properties[NODE_PROPERTY_DEFINITION]

        file_resource = \
            node_property_definition.pop('file', {})
        if file_resource:
            resource_definition = \
                _yaml_from_file(**file_resource)
        else:
            resource_definition = node_property_definition

        if 'kind' not in resource_definition.keys():
            node_type = \
                ctx.node.type if \
                isinstance(ctx.node.type, basestring) else ''
            resource_definition['kind'] = node_type.split('.')[-1]

        kwargs['resource_definition'] = \
            KubernetesResourceDefinition(
                **resource_definition)

        kwargs['mapping'] = KubernetesApiMapping(
            **ctx.node.properties[NODE_PROPERTY_API_MAPPING]
        )

        try:
            task(**kwargs)
        except (KuberentesInvalidPayloadClassError,
                KuberentesInvalidApiClassError,
                KuberentesInvalidApiMethodError) as e:
            raise NonRecoverableError(str(e))
        except Exception as e:
            raise RecoverableError(str(e))

    return wrapper


@operation
@with_kubernetes_client
@resource_task
def resource_create(client, mapping, resource_definition, **kwargs):
    ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES] =\
        client.create_resource(
            mapping,
            resource_definition,
            ctx.node.properties[NODE_PROPERTY_OPTIONS]).to_dict()


@operation
@with_kubernetes_client
@resource_task
def resource_delete(client, mapping, resource_definition, **kwargs):
    client.delete_resource(
        mapping,
        retrieve_id(ctx.instance),
        ctx.node.properties[NODE_PROPERTY_OPTIONS]
    )
