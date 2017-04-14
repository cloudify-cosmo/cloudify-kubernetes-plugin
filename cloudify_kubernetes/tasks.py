from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import RecoverableError, NonRecoverableError

from .k8s import (CloudifyKubernetesClient,
                  KubernetesApiConfigurationVariants,
                  KubernetesApiMapping,
                  KubernetesResourceDefinition,
                  KuberentesInvalidPayloadClassError,
                  KuberentesInvalidApiClassError,
                  KuberentesInvalidApiMethodError)


INSTANCE_RUNTIME_PROPERTY_KUBERNETES = 'kubernetes'
NODE_PROPERTY_API_MAPPING = '_api_mapping'
NODE_PROPERTY_CONFIGURATION = 'configuration'
NODE_PROPERTY_DEFINITION = 'definition'
NODE_PROPERTY_OPTIONS = 'options'
RELATIONSHIP_TYPE_MANAGED_BY_MASTER = 'cloudify.kubernetes.relationships.managed_by_master'


def _retrieve_master_node(resource_instance):
    for relationship in resource_instance.relationships:
        if relationship.type == RELATIONSHIP_TYPE_MANAGED_BY_MASTER:
            return relationship.target.node


def _retrieve_configuration_property(resource_instance):
    return _retrieve_master_node(resource_instance).properties.get(NODE_PROPERTY_CONFIGURATION, {})


def retrieve_id(resource_instance):
    return resource_instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES]['metadata']['name']


def _resource_task(task_operation):
    configuration_property = _retrieve_configuration_property(ctx.instance)
    resource_definition = KubernetesResourceDefinition(ctx.node.type, **ctx.node.properties[NODE_PROPERTY_DEFINITION])
    mapping = KubernetesApiMapping(**ctx.node.properties[NODE_PROPERTY_API_MAPPING])

    try:
        client = CloudifyKubernetesClient(
            KubernetesApiConfigurationVariants(ctx, configuration_property),
            ctx.logger)

        task_operation(client, mapping, resource_definition)
    except (KuberentesInvalidPayloadClassError, KuberentesInvalidApiClassError, KuberentesInvalidApiMethodError) as e:
        raise NonRecoverableError(str(e))
    except Exception as e:
        raise RecoverableError(str(e))


@operation
def resource_create(**kwargs):
    def _do_create(client, mapping, resource_definition):
        ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = \
            client.create_resource(mapping, resource_definition, ctx.node.properties[NODE_PROPERTY_OPTIONS]).to_dict()

    _resource_task(_do_create)


@operation
def resource_delete(**kwargs):
    def _do_delete(client, mapping, resource_definition):
        client.delete_resource(mapping, retrieve_id(ctx.instance), ctx.node.properties[NODE_PROPERTY_OPTIONS])

    _resource_task(_do_delete)
