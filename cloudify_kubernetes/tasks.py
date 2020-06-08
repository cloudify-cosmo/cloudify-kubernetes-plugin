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

# hack for import namespaced modules (google.auth)
import cloudify_importer # noqa

import re

from cloudify import ctx
from cloudify.exceptions import (
    OperationRetry,
    RecoverableError,
    NonRecoverableError)

from .k8s import status_mapping
from .utils import (PERMIT_REDEFINE,
                    DEFS,
                    mapping_by_data,
                    mapping_by_kind,
                    retrieve_path,
                    resource_definition_from_blueprint,
                    resource_definitions_from_file,
                    JsonCleanuper,
                    store_resource_definition,
                    retrieve_stored_resource)
from .k8s.exceptions import KuberentesApiOperationError
from .decorators import (resource_task,
                         with_kubernetes_client,
                         INSTANCE_RUNTIME_PROPERTY_KUBERNETES)


DEFAULT_NAMESPACE = 'default'
NODE_PROPERTY_FILES = 'files'
NODE_PROPERTY_OPTIONS = 'options'
FILENAMES = r'[A-Za-z0-9\.\_\-\/]*yaml\#[0-9]*'


def _retrieve_id(resource_instance, filename=None, delete=False):

    data = resource_instance.runtime_properties.get(
        INSTANCE_RUNTIME_PROPERTY_KUBERNETES, {})
    matches = [re.match(FILENAMES, key) for key in data]

    if filename and filename in data:
        if delete:
            resource = data.pop(filename)
            return resource['metadata']['name']
        return data[filename]['metadata']['name']
    elif 'metadata' in data and not any(matches):
        if delete:
            resource = data.pop('metadata')
            return resource['name']
        return data['metadata']['name']
    elif not ctx.node.properties[PERMIT_REDEFINE]:
        if filename:
            message = 'Filename {0} not found in ' \
                      'kubernetes runtime property. '.format(filename)
        else:
            message = 'Node property {0} is not True. '.format(PERMIT_REDEFINE)
    else:
        resources = resource_instance.runtime_properties[DEFS]
        if len(resources) > 0:
            return resources[-1]['metadata']['name']
        message = 'No suitable resource IDs found. '
    ctx.logger.error(
        'Cannot resolve which '
        'resource to retrieve: ' + message + 'Available data: {0}'.format(data)
    )
    # Failure will come at a later time.
    return


def _do_resource_create(client, api_mapping, resource_definition, **kwargs):
    if 'namespace' not in kwargs:
        kwargs['namespace'] = DEFAULT_NAMESPACE

    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    store_resource_definition(resource_definition)

    ctx.logger.debug('Node options {0}'.format(options))
    perform_task = ctx.instance.runtime_properties.get('__perform_task', False)
    if ctx.node.properties.get('use_external_resource') and not perform_task:
        return JsonCleanuper(client.read_resource(
            api_mapping,
            resource_definition.metadata['name'],
            options
        )).to_dict()
    return JsonCleanuper(client.create_resource(
        api_mapping,
        resource_definition,
        options
    )).to_dict()


def _do_resource_read(client, api_mapping, resource_id, **kwargs):
    if not resource_id:
        raise NonRecoverableError(
            'No resource was found in runtime properties for reading. '
            'This can occur when the node property {0} is True, and '
            'resources were created and deleted out of order.'.format(
                PERMIT_REDEFINE)
        )
    if 'namespace' not in kwargs:
        kwargs['namespace'] = DEFAULT_NAMESPACE
    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    ctx.logger.debug('Node options {0}'.format(options))
    return JsonCleanuper(client.read_resource(
        api_mapping,
        resource_id,
        options
    )).to_dict()


def _do_resource_update(client, api_mapping, resource_definition, **kwargs):
    if 'namespace' not in kwargs:
        kwargs['namespace'] = DEFAULT_NAMESPACE

    return JsonCleanuper(client.update_resource(
        api_mapping,
        resource_definition,
        ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    )).to_dict()


def _do_resource_status_check(resource_kind, response):
    ctx.logger.info('Checking resource status.')
    status_obj_name = 'Kubernetes{0}Status'.format(resource_kind)
    if hasattr(status_mapping, status_obj_name):
        return getattr(status_mapping, status_obj_name)(
            response['status'],
            ctx.node.properties['validate_resource_status']).ready()
    ctx.logger.debug(
        'Resource status check not supported for {0}'.format(
            resource_kind))
    return True


def _do_resource_delete(client, api_mapping, resource_definition,
                        resource_id, **kwargs):

    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    if 'namespace' not in options:
        options['namespace'] = DEFAULT_NAMESPACE

    # The required fields for all kubernetes resources are
    # - name
    # - namespace
    # - body

    # But the ``ReplicationController`` resource have only one required arg
    # which is namespace

    # Moreover all resources have also payload with type ``V1DeleteOptions``
    #  except ``ReplicationController`` that does not have one

    # The resource is not a type of ``ReplicationController`` then we must
    # pass all the required fields

    resource_definition, api_mapping = \
        retrieve_stored_resource(resource_definition, api_mapping)
    if not resource_id:
        resource_id = resource_definition.metadata['name']
    perform_task = ctx.instance.runtime_properties.get('__perform_task', False)
    if ctx.node.properties.get('use_external_resource') and not perform_task:
        return JsonCleanuper(client.read_resource(
            api_mapping,
            resource_id,
            options
        )).to_dict()
    return JsonCleanuper(client.delete_resource(
        api_mapping,
        resource_definition,
        resource_id,
        options,
    )).to_dict()


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind,
    use_existing=False,  # ignore already created
)
def resource_create(client, api_mapping, resource_definition, **kwargs):

    ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = \
        _do_resource_create(
            client,
            api_mapping,
            resource_definition,
            **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind,
    use_existing=True,  # get current object
)
def resource_read(client, api_mapping, resource_definition, **kwargs):
    """Attempt to resolve the lifecycle logic.
    """

    # Read All resources.
    read_response = _do_resource_read(
        client,
        api_mapping,
        _retrieve_id(ctx.instance),
        **kwargs
    )

    # Store read response.
    ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = \
        read_response

    ctx.logger.info(
        'Resource definition: {0}'.format(read_response))

    resource_type = getattr(resource_definition, 'kind')
    if resource_type:
        _do_resource_status_check(resource_type, read_response)
        ctx.logger.info(
            'Resource definition: {0}'.format(resource_type))


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind,
    use_existing=True,  # get current object
)
def resource_update(client, api_mapping, resource_definition, **kwargs):
    ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = \
        _do_resource_update(
            client,
            api_mapping,
            resource_definition,
            **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind,
    use_existing=True,  # get current object
    cleanup_runtime_properties=True,  # remove on successful run
)
def resource_delete(client, api_mapping, resource_definition, **kwargs):

    try:
        read_response = _do_resource_read(client,
                                          api_mapping,
                                          _retrieve_id(ctx.instance),
                                          **kwargs)
        ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES] \
            = read_response
    except KuberentesApiOperationError as e:
        if '"code":404' in str(e):
            ctx.logger.debug(
                'Ignoring error: {0}'.format(str(e)))
        else:
            raise RecoverableError(
                'Raising error: {0}'.format(str(e)))
    else:
        delete_response = _do_resource_delete(
            client,
            api_mapping,
            resource_definition,
            _retrieve_id(ctx.instance),
            **kwargs
        )

        perform_task = ctx.instance.runtime_properties.get('__perform_task',
                                                           False)
        if not ctx.node.properties.get(
                'use_external_resource') and perform_task:
            raise OperationRetry(
                'Delete response: {0}'.format(delete_response))


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data,
    use_existing=False,  # ignore already created
)
def custom_resource_create(client, api_mapping, resource_definition, **kwargs):
    ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = \
        _do_resource_create(
            client,
            api_mapping,
            resource_definition,
            **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data,
    use_existing=True,  # get current object
)
def custom_resource_update(client, api_mapping, resource_definition, **kwargs):
    ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = \
        _do_resource_update(
            client,
            api_mapping,
            resource_definition,
            **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data,
    use_existing=True,  # get current object
    cleanup_runtime_properties=True,  # remove on successful run
)
def custom_resource_delete(client, api_mapping, resource_definition, **kwargs):
    try:
        read_response = _do_resource_read(client,
                                          api_mapping,
                                          _retrieve_id(ctx.instance),
                                          **kwargs)
        ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES] \
            = read_response
    except KuberentesApiOperationError as e:
        if '"code":404' in str(e):
            ctx.logger.debug(
                'Ignoring error: {0}'.format(str(e)))
        else:
            raise RecoverableError(
                'Raising error: {0}'.format(str(e)))
    else:
        delete_response = _do_resource_delete(
            client,
            api_mapping,
            resource_definition,
            _retrieve_id(ctx.instance),
            **kwargs
        )
        perform_task = ctx.instance.runtime_properties.get('__perform_task',
                                                           False)
        if not ctx.node.properties.get(
                'use_external_resource') and perform_task:
            raise OperationRetry(
                'Delete response: {0}'.format(delete_response))


@with_kubernetes_client
@resource_task(
    retrieve_resources_definitions=resource_definitions_from_file,
    retrieve_mapping=mapping_by_kind,
    use_existing=False,  # ignore already created
)
def file_resource_create(client, api_mapping, resource_definition, **kwargs):
    result = _do_resource_create(
        client,
        api_mapping,
        resource_definition,
        **kwargs
    )

    if not isinstance(
        ctx.instance.runtime_properties.get(
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES), dict
    ):
        ctx.instance.runtime_properties[
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = {}

    path = retrieve_path(kwargs)
    if path:
        ctx.instance.runtime_properties[
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES][path] = result
    else:
        ctx.instance.runtime_properties[
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = result
    # force save
    ctx.instance.runtime_properties.dirty = True
    ctx.instance.update()


@with_kubernetes_client
@resource_task(
    retrieve_resources_definitions=resource_definitions_from_file,
    retrieve_mapping=mapping_by_kind,
    use_existing=True,  # get current object
)
def file_resource_read(client, api_mapping, resource_definition, **kwargs):
    """Attempt to resolve the lifecycle logic.
    """
    path = retrieve_path(kwargs)

    # Read All resources.
    read_response = _do_resource_read(
        client,
        api_mapping,
        _retrieve_id(ctx.instance, path),
        **kwargs
    )

    if not isinstance(
        ctx.instance.runtime_properties.get(
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES), dict
    ):
        ctx.instance.runtime_properties[
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = {}

    if path:
        ctx.instance.runtime_properties[
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES][path] = read_response
    else:
        ctx.instance.runtime_properties[
            INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = read_response
    # force save
    ctx.instance.runtime_properties.dirty = True
    ctx.instance.update()

    resource_type = getattr(resource_definition, 'kind')
    if resource_type:
        _do_resource_status_check(resource_type, read_response)
        ctx.logger.info(
            'Resource definition: {0}'.format(resource_type))


@with_kubernetes_client
@resource_task(
    retrieve_resources_definitions=resource_definitions_from_file,
    retrieve_mapping=mapping_by_kind,
    use_existing=True,  # get current object
    cleanup_runtime_properties=True,  # remove on successful run
)
def file_resource_delete(client, api_mapping, resource_definition, **kwargs):
    path = retrieve_path(kwargs)

    _do_resource_delete(
        client,
        api_mapping,
        resource_definition,
        _retrieve_id(ctx.instance, path, delete=True),
        **kwargs
    )


def multiple_file_resource_create(**kwargs):
    file_resources = kwargs.get(
        NODE_PROPERTY_FILES,
        ctx.node.properties.get(NODE_PROPERTY_FILES, [])
    )

    for file_resource in file_resources:
        file_resource_create(file=file_resource, **kwargs)


def multiple_file_resource_read(**kwargs):
    file_resources = kwargs.get(
        NODE_PROPERTY_FILES,
        ctx.node.properties.get(NODE_PROPERTY_FILES, [])
    )

    for file_resource in file_resources:
        file_resource_read(file=file_resource, **kwargs)


def multiple_file_resource_delete(**kwargs):
    file_resources = kwargs.get(
        NODE_PROPERTY_FILES,
        ctx.node.properties.get(NODE_PROPERTY_FILES, [])
    )

    for file_resource in file_resources:
        file_resource_delete(file=file_resource, **kwargs)
