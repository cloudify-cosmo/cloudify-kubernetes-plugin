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

from cloudify import ctx
from cloudify.exceptions import (
    OperationRetry,
    RecoverableError,
    NonRecoverableError)

from ._compat import text_type
from .k8s import (status_mapping,
                  KubernetesResourceDefinition)
from .decorators import (resource_task,
                         with_kubernetes_client)
from .k8s.exceptions import KuberentesApiOperationError
from .utils import (PERMIT_REDEFINE,
                    retrieve_id,
                    retrieve_path,
                    JsonCleanuper,
                    mapping_by_data,
                    mapping_by_kind,
                    retrieve_stored_resource,
                    retrieve_last_create_path,
                    store_result_for_retrieve_id,
                    resource_definitions_from_file,
                    resource_definition_from_blueprint,
                    set_namespace)


NODE_PROPERTY_FILES = 'files'
NODE_PROPERTY_OPTIONS = 'options'


def _do_resource_create(client, api_mapping, resource_definition, **kwargs):
    set_namespace(kwargs, resource_definition)

    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)

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
    set_namespace(kwargs)
    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    ctx.logger.debug('Node options {0}'.format(options))
    return JsonCleanuper(client.read_resource(
        api_mapping,
        resource_id,
        options
    )).to_dict()


def _do_resource_update(client, api_mapping, resource_definition, **kwargs):
    set_namespace(kwargs, resource_definition)

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


def _check_if_resource_exists(client, api_mapping, resource_id, **kwargs):
    try:
        return _do_resource_read(client, api_mapping, resource_id, **kwargs)
    except KuberentesApiOperationError:
        ctx.logger.error('The resource {0} was not found.'.format(resource_id))
        return


def _do_resource_delete(client, api_mapping, resource_definition,
                        resource_id, **kwargs):

    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    set_namespace(options, resource_definition)

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
    resource_state_function=_check_if_resource_exists
)
def resource_create(client, api_mapping, resource_definition, **kwargs):
    try:
        result = _do_resource_create(
            client,
            api_mapping,
            resource_definition,
            **kwargs)
    except KuberentesApiOperationError as e:
        if '(409)' in text_type(e):
            raise NonRecoverableError(
                'The resource {0} already exists. '
                'If you wish to use the existing resource, please toggle the '
                'runtime property use_external_resource to true.'.format(
                    resource_definition.to_dict()
                )
            )
        raise e
    store_result_for_retrieve_id(result)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind,
    use_existing=True,  # get current object
    resource_state_function=_check_if_resource_exists
)
def resource_read(client, api_mapping, resource_definition, **kwargs):
    """Attempt to resolve the lifecycle logic.
    """

    # Read All resources.
    read_response = _do_resource_read(
        client,
        api_mapping,
        retrieve_id(),
        **kwargs
    )

    # Store read response.
    store_result_for_retrieve_id(read_response)

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
    resource_state_function=_check_if_resource_exists
)
def resource_update(client, api_mapping, resource_definition, **kwargs):
    result = _do_resource_update(
        client,
        api_mapping,
        resource_definition,
        **kwargs)
    store_result_for_retrieve_id(result)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind,
    use_existing=True,  # get current object
    cleanup_runtime_properties=True,  # remove on successful run
    resource_state_function=_check_if_resource_exists
)
def resource_delete(client, api_mapping, resource_definition, **kwargs):
    resource_id = retrieve_id(ctx.instance)
    try:
        read_result = _do_resource_read(
            client, api_mapping, resource_id, **kwargs)
    except KuberentesApiOperationError as e:
        if '"code":404' in text_type(e):
            ctx.logger.debug(
                'Ignoring error: {0}'.format(text_type(e)))
        else:
            raise RecoverableError(
                'Raising error: {0}'.format(text_type(e)))
    else:
        resource_definition, api_mapping = retrieve_stored_resource(
            resource_definition, api_mapping, delete=True)
        delete_response = _do_resource_delete(
            client,
            api_mapping,
            resource_definition,
            resource_definition.metadata['name'],
            **kwargs
        )

        perform_task = ctx.instance.runtime_properties.get('__perform_task',
                                                           False)
        if not ctx.node.properties.get(
                'use_external_resource') and perform_task:
            store_result_for_retrieve_id(read_result)
            raise OperationRetry(
                'Delete response: {0}'.format(delete_response))


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data,
    use_existing=False,  # ignore already created
    resource_state_function=_check_if_resource_exists
)
def custom_resource_create(client, api_mapping, resource_definition, **kwargs):
    result = _do_resource_create(
        client,
        api_mapping,
        resource_definition,
        **kwargs)
    store_result_for_retrieve_id(result)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data,
    use_existing=True,  # get current object
)
def custom_resource_update(client, api_mapping, resource_definition, **kwargs):
    read_response = \
        _do_resource_update(
            client,
            api_mapping,
            resource_definition,
            **kwargs)
    store_result_for_retrieve_id(read_response)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data,
    use_existing=True,  # get current object
    cleanup_runtime_properties=True,  # remove on successful run
    resource_state_function=_check_if_resource_exists
)
def custom_resource_delete(client, api_mapping, resource_definition, **kwargs):
    resource_id = retrieve_id()
    try:
        read_result = _do_resource_read(
            client, api_mapping, resource_id, **kwargs)
    except KuberentesApiOperationError as e:
        if '(404)' in text_type(e):
            ctx.logger.debug(
                'Ignoring error: {0}'.format(text_type(e)))
        else:
            raise RecoverableError(
                'Raising error: {0}'.format(text_type(e)))
    else:
        resource_definition, api_mapping = retrieve_stored_resource(
            resource_definition, api_mapping, delete=True)
        delete_response = _do_resource_delete(
            client,
            api_mapping,
            resource_definition,
            resource_definition.metadata['name'],
            **kwargs
        )
        perform_task = ctx.instance.runtime_properties.get('__perform_task',
                                                           False)
        if not ctx.node.properties.get(
                'use_external_resource') and perform_task:
            store_result_for_retrieve_id(read_result)
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
    path = retrieve_path(kwargs)
    store_result_for_retrieve_id(result, path)


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
    _, resource, _ = retrieve_last_create_path(path, delete=False)

    if resource:
        resource_id = resource['metadata']['name']
    else:
        resource_id = resource_definition.metadata['name']

    # Read All resources.
    read_response = _do_resource_read(
        client,
        api_mapping,
        resource_id,
        **kwargs
    )
    store_result_for_retrieve_id(read_response, path)

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
    resource_state_function=_check_if_resource_exists
)
def file_resource_delete(client, api_mapping, resource_definition, **kwargs):
    """We want to delete the resources from the file that was created last
    with this node template."""

    path = retrieve_path(kwargs)

    try:
        path, resource, adjacent_resources = \
            retrieve_last_create_path(path)
        resource_id = resource['metadata']['name']
        resource_kind = resource['kind']
        metadata = resource['metadata']
    except (NonRecoverableError, TypeError, KeyError):
        adjacent_resources = {}
        resource_definition, api_mapping = retrieve_stored_resource(
            resource_definition, api_mapping, delete=True)
        resource_id = resource_definition.metadata['name']
    else:
        api_version = resource.get('apiVersion') or \
            resource.get('api_version')
        if not api_version:
            raise NonRecoverableError(
                'Received invalid resource '
                'with no API version: {0}'.format(resource))
        # The minimum requirements for building this object.
        resource_definition = KubernetesResourceDefinition(
            kind=resource_kind,
            apiVersion=api_version,
            metadata=metadata
        )
        api_mapping = mapping_by_kind(resource_definition)

    # We now want to see if the resource exists.
    try:
        _do_resource_read(
            client, api_mapping, resource_id, **kwargs)
    except (NonRecoverableError, KuberentesApiOperationError) as e:
        # The resource has been deleted, or something.
        if adjacent_resources and '(404)' in text_type(e):
            # We have resources from the same file, so we want to
            # put them back into the "queue" of stuff to delete.
            for k, v in adjacent_resources.items():
                store_result_for_retrieve_id(v, k)
            raise OperationRetry(
                'Continue to deletion of adjacent resources: {0}'.format(
                    text_type(e)))
        elif '(404)' in text_type(e):
            # The resource has been deleted and there are no adjacent
            # resources (that we know of).
            ctx.logger.debug(
                'Ignoring error: {0}'.format(text_type(e)))
        # elif PERMIT_REDEFINE in text_type(e):
        #     ctx.logger.debug(
        #         'Ignoring error: {0}'.format(text_type(e)))
        else:
            # Not sure what happened.
            raise RecoverableError(
                'Raising error: {0}'.format(text_type(e)))
    else:
        # We now know that the resource has not been deleted.
        delete_response = _do_resource_delete(
            client,
            api_mapping,
            resource_definition,
            resource_definition.metadata['name'],
            **kwargs
        )
        # Since the resource has only been asyncronously deleted, we
        # need to put it back in all our runtime properties in order to
        # let it be deleted again only not to be restored.
        store_result_for_retrieve_id(
            JsonCleanuper(resource_definition).to_dict(),
            path
        )
        # Also the adjacent resources:
        for k, v in adjacent_resources.items():
            store_result_for_retrieve_id(v, k)
        # And now, we rerun to hopefully fail.
        raise OperationRetry('Delete response: {0}'.format(delete_response))
    # If I have not thought of another scenario, we need to go back and
    # read the logs.
    if adjacent_resources:

        ctx.logger.info('Indeed, we arrived here.')
        for k, v in adjacent_resources.items():
            store_result_for_retrieve_id(v, k)
        raise OperationRetry('Retrying for adjacent resources.')


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
