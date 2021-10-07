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
#
import os
import sys
from tempfile import NamedTemporaryFile
from collections import OrderedDict

import yaml
from cloudify import ctx
from cloudify.manager import get_rest_client
from cloudify.utils import exception_to_error_cause
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError

try:
    from cloudify.constants import RELATIONSHIP_INSTANCE, NODE_INSTANCE
except ImportError:
    NODE_INSTANCE = 'node-instance'
    RELATIONSHIP_INSTANCE = 'relationship-instance'

from ._compat import text_type
from .k8s import (get_mapping,
                  KubernetesApiMapping,
                  KubernetesResourceDefinition,
                  KuberentesMappingNotFoundError,
                  KuberentesInvalidDefinitionError)
from .workflows import merge_definitions, DEFINITION_ADDITIONS

DEFAULT_NAMESPACE = 'default'
NODE_PROPERTY_FILE_RESOURCE_PATH = 'resource_path'
NODE_PROPERTY_API_MAPPING = 'api_mapping'
NODE_PROPERTY_DEFINITION = 'definition'
NODE_PROPERTY_FILE = 'file'
NODE_PROPERTY_FILES = 'files'
NODE_PROPERTY_OPTIONS = 'options'
DEFS = '__resource_definitions'
PERMIT_REDEFINE = 'allow_node_redefinition'
INSTANCE_RUNTIME_PROPERTY_KUBERNETES = 'kubernetes'
FILENAMES = r'[A-Za-z0-9\.\_\-\/]*yaml\#[0-9]*'
CERT_KEYS = ['ssl_ca_cert', 'cert_file', 'key_file']
CUSTOM_OBJECT_NODE_OPTIONS = ['plural', 'group', 'version']
CUSTOM_OBJECT_ANNOTATIONS = ['cloudify-crd-group',
                             'cloudify-crd-plural',
                             'cloudify-crd-version']
CLUSTER_TYPE = 'cloudify.kubernetes.resources.SharedCluster'
CLUSTER_TYPES = ['cloudify.nodes.aws.eks.Cluster',
                 'cloudify.gcp.nodes.KubernetesCluster',
                 'cloudify.nodes.gcp.KubernetesCluster',
                 'cloudify.azure.nodes.compute.ManagedCluster',
                 'cloudify.nodes.azure.compute.ManagedCluster']
CLUSTER_REL = 'cloudify.relationships.kubernetes.connected_to_shared_cluster'


def retrieve_path(kwargs):
    return kwargs\
        .get(NODE_PROPERTY_FILE, {})\
        .get(NODE_PROPERTY_FILE_RESOURCE_PATH, u'')


def match_resource(left, right):
    """Compare a dict, left, and right,either a dict or a
    KubernetesResourceDefinition, for equivalence.

    :param left: a dict
    :param right: a dict or a KubernetesResourceDefinition
    :return: bool
    """
    l_name = left.get('metadata', {}).get('name')
    l_kind = left.get('kind')
    l_namesp = left.get('metadata', {}).get('namespace', 'default')
    if isinstance(right, KubernetesResourceDefinition):
        r_name = right.metadata.get('name')
        r_namesp = right.metadata.get('namespace', 'default')
        r_kind = right.kind
    else:
        r_name = right.get('metadata', {}).get('name')
        r_namesp = right.get('metadata', {}).get('namespace', 'default')
        r_kind = right.get('kind')
    if all([l_name == r_name, l_kind == r_kind, l_namesp == r_namesp]):
        return True
    return False


def retrieve_last_create_path(file_name=None, delete=True):
    """We want to find out the last path that was used to create resources."""

    # The filename comes from the blueprint.
    # If this is a deployment update, the name of the file might have changed.

    # There are two places where data is stored about resources.
    # The first is by filename, plus the data from the file in the blueprint.
    file_resources = OrderedDict(ctx.instance.runtime_properties.get(
        INSTANCE_RUNTIME_PROPERTY_KUBERNETES, {}))
    # The second stores the defintion object.
    resource_definitions = ctx.instance.runtime_properties.get(DEFS, [])

    # This is the resource from a file.
    file_resource = None
    # These are other resources from the same file.
    adjacent_resources = {}

    try:
        # We try to get the resource definition as it appeared in the file.
        if delete:
            file_resource = file_resources.pop(file_name)
        else:
            return file_name, file_resources[file_name], adjacent_resources
    except KeyError:
        # If this is a deployment update, the name of the file might have
        # changed. So the name of the file that we got originally
        # might be the name of the new file.
        # If that's the case, then we get the most recently added resource
        # definition as the resource that we want to delete.
        try:
            if delete:
                resource_definition = resource_definitions.pop()
            else:
                resource_definition = resource_definitions[-1]
        except IndexError:
            raise NonRecoverableError('No resource could be resolved.')

        # We now want to get the file that was in that resource.
        for file_name, file_resource in file_resources.items():
            if match_resource(resource_definition, file_resource):
                break

    if delete and file_name in file_resources:
        del file_resources[file_name]

    if not file_resource:
        return file_name, file_resource, adjacent_resources

    adjacent_file_name, _ = file_name.split('.yaml')

    for _f, _r in list(file_resources.items()):
        if adjacent_file_name in _f and not match_resource(_r, file_resource):
            adjacent_resources.update({_f: _r})
            if delete:
                del file_resources[_f]

    ctx.instance.runtime_properties[
        INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = file_resources
    ctx.instance.runtime_properties[DEFS] = resource_definitions

    # force save
    ctx.instance.runtime_properties.dirty = True
    ctx.instance.update()

    return file_name, file_resource, adjacent_resources


def generate_traceback_exception():
    _, exc_value, exc_traceback = sys.exc_info()
    response = exception_to_error_cause(exc_value, exc_traceback)
    return response


def _yaml_from_files(
        resource_path,
        target_path=None,
        template_variables=None):

    template_variables = template_variables or {}

    downloaded_file_path = \
        ctx.download_resource_and_render(
            resource_path,
            target_path,
            template_variables)

    # Validate file size
    if os.path.isfile(downloaded_file_path) \
            and os.path.getsize(downloaded_file_path) == 0:
        raise KuberentesInvalidDefinitionError(
            'Invalid resource file definition.'
        )

    with open(downloaded_file_path, 'rb') as outfile:
        file_content = outfile.read()

    # Validate file content if it contains at least one dict
    file_content = file_content.strip()
    if len(list(yaml.load_all(file_content))) == 0:
        raise KuberentesInvalidDefinitionError(
            'Invalid resource file definition.'
        )

    return yaml.load_all(file_content)


def mapping_by_data(**kwargs):
    mapping_data = kwargs.get(
        NODE_PROPERTY_API_MAPPING,
        ctx.node.properties.get(NODE_PROPERTY_API_MAPPING, None)
    )

    if mapping_data:
        return KubernetesApiMapping(**mapping_data)

    raise KuberentesMappingNotFoundError(
        'Cannot find API mapping for this request - '
        '"api_mapping" property data is invalid'
    )


def mapping_by_kind(resource_definition, node_options=None, **_):
    node_options = node_options or []
    try:
        annotations = resource_definition.metadata.get(
            'annotations', {}).keys()
    except AttributeError:
        pass
    else:
        if set(CUSTOM_OBJECT_ANNOTATIONS).issubset(set(annotations)):
            return get_mapping(kind='CustomObjectsApi')
    try:
        return get_mapping(kind=resource_definition.kind)
    except KuberentesMappingNotFoundError:
        if set(CUSTOM_OBJECT_NODE_OPTIONS).issubset(set(node_options)):
            return get_mapping(kind='CustomObjectsApi')
        raise


def get_definition_object(**kwargs):

    def resolve_kind():
        if 'cloudify.kubernetes.resources.BlueprintDefinedResource' \
                in ctx.node.type_hierarchy:
            return ctx.node.type_hierarchy[-1]
        return ''

    definition = kwargs.get(
        NODE_PROPERTY_DEFINITION,
        ctx.node.properties.get(NODE_PROPERTY_DEFINITION, None)
    )
    if DEFINITION_ADDITIONS in kwargs:
        definition = merge_definitions(
            definition,
            kwargs.pop(DEFINITION_ADDITIONS))

    if not definition:
        raise KuberentesInvalidDefinitionError(
            'Incorrect format of resource definition'
        )

    if 'kind' not in definition:
        definition['kind'] = resolve_kind()

    return definition


def resource_definition_from_blueprint(**kwargs):
    definition = get_definition_object(**kwargs)
    return KubernetesResourceDefinition(**definition)


def resource_definitions_from_file(**kwargs):
    file_resource = kwargs.get(
        NODE_PROPERTY_FILE,
        ctx.node.properties.get(NODE_PROPERTY_FILE, None)
    )

    validate_file_resource(file_resource)

    resource_defs = []
    for definition in _yaml_from_files(**file_resource):
        if not isinstance(definition, dict):
            ctx.logger.warn('Unexpected {d} definition.'.format(d=definition))
            continue
        resource_defs.append(KubernetesResourceDefinition(**definition))
    return resource_defs


def resource_definition_from_payload(**kwargs):
    payload = kwargs.get('payload')
    return KubernetesResourceDefinition(**yaml.load(payload))


def validate_file_resource(file_resource):
    if not file_resource or not isinstance(file_resource, dict):
        raise NonRecoverableError(
            'Invalid resource file specification. '
            'The file properties must be a dictionary with the keys: '
            'resource_path (required), template_variables, and target_path. '
            'File resource: {file_resource}'.format(
                file_resource=file_resource)
        )


def validate_file_resources(file_resources):
    if not file_resources or not isinstance(file_resources, list):
        raise NonRecoverableError(
            'Invalid resource file specification. '
            'The file properties must be a list of dictionaries with the keys:'
            ' resource_path (required), template_variables, and target_path. '
            'File resource: {file_resource}'.format(
                file_resource=file_resources)
        )


def get_instance(_ctx):
    if _ctx.type == RELATIONSHIP_INSTANCE:
        return _ctx.source.instance
    else:  # _ctx.type == NODE_INSTANCE
        return _ctx.instance


def get_node(_ctx):
    if _ctx.type == RELATIONSHIP_INSTANCE:
        return _ctx.source.node
    else:  # _ctx.type == NODE_INSTANCE
        return _ctx.node


class JsonCleanuper(object):

    def __init__(self, ob):
        if isinstance(ob, dict):
            resource = ob
        else:
            resource = ob.to_dict()

        if isinstance(resource, list):
            self._cleanuped_list(resource)
        elif isinstance(resource, dict):
            self._cleanuped_dict(resource)

        self.value = resource

    def _cleanuped_list(self, resource):
        for k, v in enumerate(resource):
            if not v:
                continue
            if isinstance(v, list):
                self._cleanuped_list(v)
            elif isinstance(v, dict):
                self._cleanuped_dict(v)
            elif not isinstance(v, int) and not \
                    isinstance(v, text_type):
                resource[k] = text_type(v)

    def _cleanuped_dict(self, resource):
        for k in resource:
            if not resource[k]:
                continue
            if isinstance(resource[k], list):
                self._cleanuped_list(resource[k])
            elif isinstance(resource[k], dict):
                self._cleanuped_dict(resource[k])
            elif not isinstance(resource[k], int) and not \
                    isinstance(resource[k], text_type):
                resource[k] = text_type(resource[k])

    def to_dict(self):
        return self.value


def store_resource_definition(resource_definition):
    if DEFS not in ctx.instance.runtime_properties:
        ctx.instance.runtime_properties[DEFS] = []
    ctx.logger.info('Trying: {0}'.format(resource_definition.to_dict()))
    for index, li in enumerate(ctx.instance.runtime_properties.get(DEFS, [])):
        if match_resource(li, resource_definition):
            # We found a match but still updating the resource definition
            # because fields like metadata.labels can change.

            ctx.instance.runtime_properties.get(DEFS)[
                index] = JsonCleanuper(resource_definition).to_dict()
            return
    ctx.logger.info('Adding: {0}'.format(resource_definition))
    ctx.instance.runtime_properties[DEFS].append(
        JsonCleanuper(resource_definition).to_dict())


def remove_resource_definition(resource_kind, resource_name):
    resource_definitions = ctx.instance.runtime_properties[DEFS]
    ctx.logger.info('REMOVE {0} {1}'.format(resource_kind, resource_name))
    c = 0
    for list_item in resource_definitions:
        ctx.logger.info('Checking list item {0}'.format(list_item))
        if list_item['kind'] == resource_kind and \
                list_item['metadata']['name'] == \
                resource_name:
            ctx.logger.info(
                'Deleting item {0}'.format(resource_definitions[c]))
            del resource_definitions[c]
        c += 1
    ctx.instance.runtime_properties[DEFS] = resource_definitions
    # force save
    ctx.instance.runtime_properties.dirty = True
    ctx.instance.update()


def retrieve_stored_resource(resource_definition, api_mapping, delete=False):

    node_resource_definitions = ctx.instance.runtime_properties[DEFS]
    json_resource_definition = JsonCleanuper(resource_definition).to_dict()
    try:
        stored_resource_definition = node_resource_definitions.pop()
    except IndexError:
        ctx.logger.error('No stored resource definitions found.')
        stored_resource_definition = json_resource_definition
    allow_node_definition = ctx.node.properties[PERMIT_REDEFINE]
    node_options = ctx.node.properties[NODE_PROPERTY_OPTIONS].keys()
    if (json_resource_definition != stored_resource_definition) and \
            allow_node_definition:
        ctx.logger.error(
            'The resource definiton that was provided is different '
            'from that stored from the previous modification. '
            'Using the previous resource.'
        )
        ctx.logger.debug(
            'Provided resource definition: {0}'.format(
                json_resource_definition)
        )
        ctx.logger.debug(
            'Stored resource definition: {0}'.format(
                stored_resource_definition)
        )
        resource_definition = KubernetesResourceDefinition(
            **stored_resource_definition)
        api_mapping = mapping_by_kind(
            resource_definition, node_options=node_options)
    if delete:
        remove_resource_definition(
            resource_definition.kind,
            resource_definition.metadata['name'])
    ctx.instance.runtime_properties.dirty = True
    ctx.instance.update()

    return resource_definition, api_mapping


def retrieve_id(delete=False):

    data = ctx.instance.runtime_properties.get(
        INSTANCE_RUNTIME_PROPERTY_KUBERNETES, {})

    if delete:
        # We do not need to find the whole shared_path stuff when
        # we are not dealing with a file.
        resource = data.pop('metadata')
        resource_id = resource['name']
    else:
        resource_id = data['metadata']['name']

    ctx.instance.runtime_properties[
        INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = data
    # force save
    ctx.instance.runtime_properties.dirty = True
    ctx.instance.update()
    return resource_id


def store_result_for_retrieve_id(result, path=None):

    store_resource_definition(
        KubernetesResourceDefinition(
            result['kind'],
            result.get('api_version', result.get('apiVersion')),
            result['metadata']
        )
    )

    if not isinstance(
        ctx.instance.runtime_properties.get(
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES), dict
    ):
        ctx.instance.runtime_properties[
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = {}

    if path:
        ctx.instance.runtime_properties[
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES][path] = result
    else:
        ctx.instance.runtime_properties[
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = result
    # force save
    ctx.instance.runtime_properties.dirty = True
    ctx.instance.update()


def set_namespace(kwargs, resource_definition=None):
    resource_definition = resource_definition or {}
    if isinstance(resource_definition, dict):
        namespace = resource_definition.get('metadata', {}).get('namespace')
    elif isinstance(resource_definition, KubernetesResourceDefinition):
        namespace = resource_definition.metadata.get('namespace')
    else:
        node_instance = get_instance(ctx)
        namespaces = [x for x in node_instance.relationships if
                      'cloudify.kubernetes.resources.Namespace' in
                      x.target.node.type_hierarchy]
        if not namespaces:
            namespace = DEFAULT_NAMESPACE
        else:
            if len(namespaces) != 1:
                ctx.logger.warn('Attempting to resolve missing namespace. '
                                'Exactly one relationship to a Namespace '
                                'node type was not found. Ignoring.')
            target = namespaces[0]
            data = target.instance.runtime_properties.get(
                INSTANCE_RUNTIME_PROPERTY_KUBERNETES, {})
            namespace = data['metadata']['name']
    kwargs['namespace'] = namespace


def set_custom_resource(kwargs,
                        resource_definition=None,
                        group=None,
                        plural=None,
                        version=None,
                        **_):
    """For custom objects, we need to provide in the kwargs, the group plural,
    and version keys. This is how we handled it for namespace. There is really
    no ideal way to do this, because there is not a universal way
    to define custom objects in Kubernetes.

    So we rely on user input in metadata.

    :param kwargs:
    :param resource_definition:
    :param group:
    :param plural:
    :param version:
    :return:
    """
    resource_definition = resource_definition or {}
    annotations = {}
    if isinstance(resource_definition, dict):
        annotations = resource_definition.get(
            'metadata', {}).get('annotations', {})
    elif isinstance(resource_definition, KubernetesResourceDefinition):
        annotations = resource_definition.metadata.get('annotations', {})
    if annotations is None:
        annotations = {}
    group = annotations.get(
        'cloudify-crd-group', group or kwargs.get('group'))
    plural = annotations.get(
        'cloudify-crd-plural', plural or kwargs.get('plural'))
    version = annotations.get(
        'cloudify-crd-version', version or kwargs.get('version'))
    if group and plural and version:
        kwargs.update({
            'group': group,
            'plural': plural,
            'version': version})


def create_tempfiles_for_certs_and_keys(config):
    for prop in CERT_KEYS:
        current_value = config.get('api_options', {}).get(prop)
        if current_value and not os.path.isfile(current_value):
            fin = NamedTemporaryFile('w', suffix='__cfy.k8s__', delete=False)
            fin.write(current_value)
            fin.close()
            config['api_options'][prop] = fin.name
    return config


def delete_tempfiles_for_certs_and_keys(config):
    for prop in CERT_KEYS:
        current_value = config.get('api_options', {}).get(prop, '')
        if current_value and current_value.endswith('__cfy.k8s__'):
            os.remove(current_value)


def handle_existing_resource(resource_exists, definition):
    expected = ctx.node.properties.get('use_external_resource', False)
    create_anyway = ctx.node.properties.get('create_if_missing', False)
    use_anyway = ctx.node.properties.get('use_if_exists', True)

    no_create = (resource_exists and expected) or \
                (resource_exists and not expected and use_anyway)
    create = (not resource_exists and not expected) or \
             (not resource_exists and expected and create_anyway)

    if no_create:
        ctx.logger.info('The resource {r} exists. Not executing operation.'
                        .format(r=definition.to_dict()))
        ctx.instance.runtime_properties['__perform_task'] = False
    elif create:
        ctx.instance.runtime_properties['__perform_task'] = True
    else:
        ctx.logger.info('Expected resource {r} to exist, but it does not and '
                        'create_if_missing is {cim}. Not executing operation.'
                        .format(r=definition.to_dict(), cim=create_anyway))
        ctx.instance.runtime_properties['__perform_task'] = False


def handle_delete_resource(resource_exists):
    expected = ctx.node.properties.get('use_external_resource', False)

    if resource_exists and expected:
        ctx.logger.info('The resource {r} exists as expected. '
                        'Not executing operation.'.format(r=resource_exists))
        ctx.instance.runtime_properties['__perform_task'] = False
    else:
        ctx.instance.runtime_properties['__perform_task'] = True


def with_rest_client(func):
    """
    :param func: This is a class for the aws resource need to be
    invoked
    :return: a wrapper object encapsulating the invoked function
    """

    def wrapper_inner(*args, **kwargs):
        kwargs['rest_client'] = get_rest_client()
        return func(*args, **kwargs)
    return wrapper_inner


@with_rest_client
def get_deployment_node_instances(deployment_id, rest_client):
    try:
        return rest_client.node_instances.list(
            deployment_id=deployment_id,
            _include=['id', 'node_id', 'runtime_properties'])
    except CloudifyClientError:
        return


@with_rest_client
def get_node_rest(deployment_id, node_id, rest_client):
    try:
        return rest_client.nodes.get(
            deployment_id=deployment_id,
            node_id=node_id,
            _include=['type_hierarchy'])
    except CloudifyClientError:
        return


@with_rest_client
def execute_workflow(deployment_id, workflow_id, parameters, rest_client):
    return rest_client.executions.start(deployment_id=deployment_id,
                                        workflow_id=workflow_id,
                                        parameters=parameters,
                                        allow_custom_parameters=True)


def get_kubernetes_cluster_node_instance_id(deployment_id):
    for node_instance in get_deployment_node_instances(deployment_id):
        node = get_node_rest(deployment_id, node_instance.node_id)
        for node_type in node.type_hierarchy:
            if node_type in CLUSTER_TYPES:
                return node_instance.id
    raise NonRecoverableError(
        'The shared resource does not contain a supported Kubernetes Cluster '
        'in node types {types}'.format(types=CLUSTER_TYPES))


def get_client_config(**kwargs):
    """We might get the client config from kwargs (node properties), or from
    a relationship to a shared cluster.

    :param kwargs: from node properties
    :return:
    """

    # It probably happens in a NI context, but maybe it happens in a
    # relationship.
    # It is problematic to program for just NI. Leads to problem later on.
    node_instance = get_instance(ctx)
    for x in node_instance.relationships:
        if CLUSTER_REL in x.type_hierarchy and \
                CLUSTER_TYPE in x.target.node.type_hierarchy:
            # If we have a relationship to a shared cluster,
            # Then lets build the client config based on its runtime
            # properties, which are set in the post start operation.
            endpoint = x.target.instance.runtime_properties['k8s-ip']
            token = x.target.instance.runtime_properties['k8s-service-account-token']  # noqa
            ssl_ca_cert = x.target.instance.runtime_properties['k8s-cacert']
            return {
                'configuration': {
                    'api_options': {
                        'host': endpoint,
                        'api_key': token,
                        'debug': False,
                        'verify_ssl': True,
                        'ssl_ca_cert': ssl_ca_cert
                    }
                }
            }
    return kwargs.get('client_config')
