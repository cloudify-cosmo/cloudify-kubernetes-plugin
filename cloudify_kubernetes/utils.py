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

import yaml
from cloudify import ctx
from cloudify.utils import exception_to_error_cause

from ._compat import text_type
from .k8s import (get_mapping,
                  KubernetesApiMapping,
                  KubernetesResourceDefinition,
                  KuberentesMappingNotFoundError,
                  KuberentesInvalidDefinitionError)
from .workflows import merge_definitions, DEFINITION_ADDITIONS

from cloudify.exceptions import NonRecoverableError
try:
    from cloudify.constants import RELATIONSHIP_INSTANCE, NODE_INSTANCE
except ImportError:
    NODE_INSTANCE = 'node-instance'
    RELATIONSHIP_INSTANCE = 'relationship-instance'

NODE_PROPERTY_FILE_RESOURCE_PATH = 'resource_path'
NODE_PROPERTY_API_MAPPING = 'api_mapping'
NODE_PROPERTY_DEFINITION = 'definition'
NODE_PROPERTY_FILE = 'file'
NODE_PROPERTY_OPTIONS = 'options'
DEFS = '__resource_definitions'
PERMIT_REDEFINE = 'allow_node_redefinition'
INSTANCE_RUNTIME_PROPERTY_KUBERNETES = 'kubernetes'
FILENAMES = r'[A-Za-z0-9\.\_\-\/]*yaml\#[0-9]*'


def retrieve_path(kwargs):
    return kwargs\
        .get(NODE_PROPERTY_FILE, {})\
        .get(NODE_PROPERTY_FILE_RESOURCE_PATH, u'')


def retrieve_last_create_path(file_name=None, delete=True):
    """We want to find out the last path that was used to create resources."""

    ctx.logger.info('Looking for file_name: {0}'.format(file_name))

    # The filename comes from the blueprint.
    # If this is a deployment update, the name of the file might have changed.

    # There are two places where data is stored about resources.
    # The first is by filename, plus the data from the file in the blueprint.
    file_resources = ctx.instance.runtime_properties.get(
        INSTANCE_RUNTIME_PROPERTY_KUBERNETES, {})
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
            resource_definition = resource_definitions.pop()
        except IndexError:
            raise NonRecoverableError('No resource could be resolved.')

        # We now want to get the file that was in that resource.
        for file_name, file_resource in list(file_resources.items()):
            if resource_definition['metadata']['name'] == \
                    file_resource['metadata']['name'] and \
                    resource_definition['kind'] == file_resource['kind']:
                del file_resources[file_name]
                break

    resource_id = file_resource.get('metadata', {}).get('name')
    resource_kind = file_resource.get('kind')

    adjacent_file_name, _ = file_name.split('.yaml')

    for _f, _r in (file_resources.items()):
        _r_name = _r['metadata']['name']
        if adjacent_file_name in _f and \
                (_r_name != resource_id or _r['kind'] != resource_kind):
            ctx.logger.info('updated ad res with {0}'.format({_f: _r}))
            adjacent_resources.update({_f: _r})
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


def mapping_by_kind(resource_definition, **kwargs):
    return get_mapping(kind=resource_definition.kind)


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

    if not file_resource:
        raise KuberentesInvalidDefinitionError(
            'Invalid resource file definition.'
        )

    return [KubernetesResourceDefinition(**definition)
            for definition in _yaml_from_files(**file_resource)]


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
    for li in ctx.instance.runtime_properties.get(DEFS, []):
        if li['kind'] == resource_definition.kind and \
                li['metadata']['name'] == resource_definition.metadata['name']:
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
        api_mapping = mapping_by_kind(resource_definition)
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
