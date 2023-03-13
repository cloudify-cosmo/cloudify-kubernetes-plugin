# Copyright (c) 2017-2023 Cloudify Platform Ltd. All rights reserved
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
import os
import base64
from copy import deepcopy

import cloudify_importer # noqa
from cloudify import ctx
from cloudify.exceptions import (
    OperationRetry,
    RecoverableError,
    NonRecoverableError)


from .._compat import text_type
from ..k8s import KubernetesResourceDefinition
from ..decorators import (resource_task,
                          nested_resource_task,
                          with_kubernetes_client)
from ..k8s.exceptions import KuberentesApiOperationError
from ..utils import (check_drift,
                     retrieve_path,
                     JsonCleanuper,
                     mapping_by_data,
                     mapping_by_kind,
                     get_archive_from_github_url,
                     NODE_PROPERTY_FILES,
                     DEFINITION_ADDITIONS,
                     update_with_additions,
                     handle_delete_resource,
                     validate_file_resources,
                     handle_existing_resource,
                     retrieve_stored_resource,
                     retrieve_last_create_path,
                     get_result_for_retrieve_id,
                     store_result_for_retrieve_id,
                     resource_definitions_from_file,
                     resource_definition_from_payload,
                     resource_definition_from_blueprint,)

from .api_calls import (
    _do_resource_read,
    _do_resource_create,
    _do_resource_delete,
    _do_resource_update,
    _check_if_resource_exists,
    _do_resource_status_check)
from .nested_resources.tokens import (
    get_service_account_payload,
    get_cluster_role_binding_payload,
    get_secret_payload)

from cloudify_common_sdk.resource_downloader import get_shared_resource

from cloudify_common_sdk.utils import get_node_instance_dir, copy_directory


def _resource_create(client, api_mapping, resource_definition, **kwargs):
    try:
        return _do_resource_create(
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


def _resource_read(client, api_mapping, resource_definition, **kwargs):
    return _do_resource_read(
        client, api_mapping, resource_definition, **kwargs)


def _resource_update(client, api_mapping, resource_definition, **kwargs):
    return _do_resource_update(
        client,
        api_mapping,
        resource_definition,
        **kwargs)


def _file_resource_create(client, api_mapping, resource_definition, **kwargs):
    result = _check_if_resource_exists(
        client, api_mapping, resource_definition, **kwargs)
    handle_existing_resource(result, resource_definition)
    perform_task = ctx.instance.runtime_properties.get('__perform_task',
                                                       False)
    if perform_task:
        result = _do_resource_create(
            client,
            api_mapping,
            resource_definition,
            **kwargs
        )
    path = retrieve_path(kwargs)
    store_result_for_retrieve_id(result, path)


def _create_kustomize(client, api_mapping, resource_definition, **kwargs):
    directory_path = ctx.node.properties['kustomize']
    name = directory_path.split('/')[-1]
    target_path = os.path.join(get_node_instance_dir(), name)

    if 'github' in directory_path .split('/')[0]:
        download_url = get_archive_from_github_url(directory_path)
        get_shared_resource(download_url, dir=target_path)
    elif os.path.isabs(directory_path):
        ctx.download_resource(directory_path, target_path=target_path)
    else:
        raise NonRecoverableError('Unsupported argument: {}'.format(directory_path))

    ctx.instance.runtime_properties['kustomize'] = target_path


def _file_resource_update(client, api_mapping, resource_definition, **kwargs):

    result = _do_resource_update(
        client,
        api_mapping,
        resource_definition,
        **kwargs
    )
    path = retrieve_path(kwargs)
    store_result_for_retrieve_id(result, path)


def _resource_check_status(client,
                           api_mapping,
                           resource_definition,
                           **kwargs):
    """Attempt to resolve the lifecycle logic.
    """
    # If check status is called during heal,
    # I want to see this happen instead of tearing down everything.
    try:
        _healable_resource_check_status(
            client, api_mapping, resource_definition, **kwargs)
    except KuberentesApiOperationError:
        if ctx.workflow_id == 'heal' and \
               ctx.operation.retry_number == 0 and \
               'check_status' in ctx.operation.name:
            ctx.instance.runtime_properties['__perform_task'] = True
            _resource_create(
                client, api_mapping, resource_definition, **kwargs)
            raise OperationRetry(
                'Attempted to heal resource, retrying check status.')
        else:
            raise


def _healable_resource_check_status(client,
                                    api_mapping,
                                    resource_definition,
                                    **kwargs):
    read_response = _do_resource_read(
        client, api_mapping, resource_definition, **kwargs)
    resource_type = getattr(resource_definition, 'kind')
    if resource_type:
        status_check = _do_resource_status_check(resource_type, read_response)
        ctx.logger.info('Resource definition: {0}'.format(resource_type))
        ctx.logger.info('Status: {0}'.format(status_check))
        if not status_check:
            raise RuntimeError('Bad status received from Kubernetes.')


def _resource_check_drift(client, api_mapping, resource_definition, **kwargs):
    """Attempt to resolve the lifecycle logic.
    """
    path = retrieve_path(kwargs)

    previous_response = get_result_for_retrieve_id(path)

    # Read All resources.
    current_response = _resource_read(
        client, api_mapping, resource_definition, **kwargs)

    diff = check_drift(previous_response, current_response)
    if diff:
        raise RuntimeError('The resource has drifted: {}'.format(diff))
    else:
        ctx.logger.info('No drift ')


def _file_resource_read(client, api_mapping, resource_definition, **kwargs):
    """Attempt to resolve the lifecycle logic.
    """
    path = retrieve_path(kwargs)
    _, resource, _ = retrieve_last_create_path(path, delete=False)

    # Read All resources.
    read_response = _do_resource_read(
        client, api_mapping, resource_definition, **kwargs)
    store_result_for_retrieve_id(read_response, path)

    resource_type = getattr(resource_definition, 'kind')
    if resource_type:
        _do_resource_status_check(resource_type, read_response)
        ctx.logger.info(
            'Resource definition: {0}'.format(resource_type))


def _get_path_with_adjacent_resources(path, resource_definition, api_mapping):
    try:
        path, resource, adjacent_resources = \
            retrieve_last_create_path(path)
        resource_kind = resource['kind']
        metadata = resource['metadata']
    except (NonRecoverableError, TypeError, KeyError):
        adjacent_resources = {}
        resource_definition, api_mapping = retrieve_stored_resource(
            resource_definition, api_mapping, delete=True)
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
    return adjacent_resources, resource_definition, api_mapping


class MissingResource(OperationRetry):
    pass


def _read_while_adjacent_resources(client,
                                   api_mapping,
                                   resource_definition,
                                   kwargs):
    try:
        _do_resource_read(client, api_mapping, resource_definition, **kwargs)
    except (NonRecoverableError, KuberentesApiOperationError) as e:
        exception = text_type(e)
        if '(404)' in exception:
            return MissingResource(exception)
        else:
            # Not sure what happened.
            return RecoverableError('Raising error: {0}'.format(exception))


def _delete_while_adjacent_resources(client,
                                     api_mapping,
                                     resource_definition,
                                     kwargs,
                                     path,
                                     adjacent_resources):

    try:
        delete_response = _do_resource_delete(
            client,
            api_mapping,
            resource_definition,
            resource_definition.metadata['name'],
            **kwargs
        )
    except KuberentesApiOperationError as exception:
        if '(404)' in exception:
            return MissingResource(exception)
        else:
            raise
    # Since the resource has only been asyncronously deleted, we
    # need to put it back in all our runtime properties in order to
    # let it be deleted again only not to be restored.
    handle_delete_resource(resource_definition)
    perform_task = ctx.instance.runtime_properties.get('__perform_task',
                                                       False)

    if "'finalizers': ['kubernetes.io/pvc-protection']" in \
            text_type(delete_response):
        prepare_pvc_delete(
            resource_definition, client, api_mapping, kwargs)

    if perform_task:
        store_result_for_retrieve_id(
            JsonCleanuper(resource_definition).to_dict(),
            path
        )
        # Also the adjacent resources:
        for k, v in adjacent_resources.items():
            store_result_for_retrieve_id(v, k)
        # And now, we rerun to hopefully fail.
        return OperationRetry('Delete response: {0}'.format(delete_response))


def _file_resource_delete(client, api_mapping, resource_definition, **kwargs):
    """We want to delete the resources from the file that was created last
    with this node template."""

    path = retrieve_path(kwargs)
    adjacent_resources, resource_definition, api_mapping = \
        _get_path_with_adjacent_resources(
            path, resource_definition, api_mapping)
    read_resource = _read_while_adjacent_resources(
        client, api_mapping, resource_definition, kwargs)
    if isinstance(read_resource, MissingResource) and adjacent_resources:
        for key, value in adjacent_resources.items():
            inner_kind = value.get('kind')
            inner_api = value.get('api_version')
            inner_meta = value.get('metadata')
            if all([inner_meta, inner_api, inner_kind]):
                inner_resource_definition = KubernetesResourceDefinition(
                    kind=inner_kind,
                    apiVersion=inner_api,
                    metadata=inner_meta
                )
                inner_api_mapping = mapping_by_kind(resource_definition)
                _file_resource_delete(
                    client,
                    inner_api_mapping,
                    inner_resource_definition,
                    **kwargs)

        for k, v in adjacent_resources.items():
            store_result_for_retrieve_id(v, k)
        raise OperationRetry(
            'Continue to deletion of adjacent resources: {0}'.format(
                text_type(read_resource)))
    elif isinstance(read_resource, MissingResource):
        ctx.logger.debug('Ignoring error: {0}'.format(
            text_type(read_resource)))
    elif isinstance(read_resource, Exception):
        raise read_resource
    else:
        result = _delete_while_adjacent_resources(
            client,
            api_mapping,
            resource_definition,
            kwargs,
            path,
            adjacent_resources)
        if isinstance(result, MissingResource):
            ctx.logger.info('Ignoring missing resource: {}'.format(
                str(result)))
        elif isinstance(result, OperationRetry):
            raise result

    # If I have not thought of another scenario, we need to go back and
    # read the logs.
    if adjacent_resources:

        ctx.logger.info('Indeed, we arrived here.')
        for k, v in adjacent_resources.items():
            store_result_for_retrieve_id(v, k)
        raise OperationRetry('Retrying for adjacent resources.')


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind,
    resource_state_function=_check_if_resource_exists
)
def resource_create(client, api_mapping, resource_definition, **kwargs):
    result = _resource_create(
        client, api_mapping, resource_definition, **kwargs)
    store_result_for_retrieve_id(result)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_payload,
    retrieve_mapping=mapping_by_kind,
)
def resource_create_from_payload(client,
                                 api_mapping,
                                 resource_definition,
                                 **kwargs):
    try:
        _resource_create(
            client, api_mapping, resource_definition, **kwargs)
    except Exception as e:
        if '409' not in text_type(e) and 'already exists' not in text_type(e):
            raise
    finally:
        result = _do_resource_read(
            client, api_mapping, resource_definition, **kwargs)
    return result


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data,
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
    retrieve_resources_definitions=resource_definitions_from_file,
    retrieve_mapping=mapping_by_kind,
)
def file_resource_create(client, api_mapping, resource_definition, **kwargs):
    _file_resource_create(client, api_mapping, resource_definition, **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resources_definitions=resource_definitions_from_file,
    retrieve_mapping=mapping_by_kind,
)
def create_kustomize(client, api_mapping, resource_definition, **kwargs):
    _create_kustomize(client, api_mapping, resource_definition, **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resources_definitions=resource_definitions_from_file,
    retrieve_mapping=mapping_by_kind,
)
def file_resource_update(client, api_mapping, resource_definition, **kwargs):
    additions = kwargs.get(DEFINITION_ADDITIONS)
    if additions:
        definition = update_with_additions(resource_definition, additions)
        resource_definition = KubernetesResourceDefinition(**definition)
    _file_resource_update(client, api_mapping, resource_definition, **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data,
    resource_state_function=_check_if_resource_exists
)
def custom_resource_read(client, api_mapping, resource_definition, **kwargs):
    read_response = _resource_read(
        client, api_mapping, resource_definition, **kwargs)

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
    retrieve_mapping=mapping_by_data,
    resource_state_function=_check_if_resource_exists
)
def custom_check_status(client, api_mapping, resource_definition, **kwargs):
    _resource_check_status(client, api_mapping, resource_definition, **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data,
    resource_state_function=_check_if_resource_exists
)
def custom_check_drift(client, api_mapping, resource_definition, **kwargs):
    _resource_check_drift(client, api_mapping, resource_definition, **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind,
    resource_state_function=_check_if_resource_exists
)
def resource_read(client, api_mapping, resource_definition, **kwargs):
    """Attempt to resolve the lifecycle logic.
    """

    # Read All resources.
    read_response = _resource_read(
        client, api_mapping, resource_definition, **kwargs)

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
)
def resource_read_check_status(client,
                               api_mapping,
                               resource_definition,
                               **kwargs):
    _resource_check_status(client, api_mapping, resource_definition, **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind,
)
def resource_read_check_drift(client,
                              api_mapping,
                              resource_definition,
                              **kwargs):
    _resource_check_drift(client, api_mapping, resource_definition, **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_payload,
    retrieve_mapping=mapping_by_kind,
)
def resource_read_from_payload(client,
                               api_mapping,
                               resource_definition,
                               **kwargs):
    return _resource_read(
        client, api_mapping, resource_definition, **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resources_definitions=resource_definitions_from_file,
    retrieve_mapping=mapping_by_kind,
)
def file_resource_read(client, api_mapping, resource_definition, **kwargs):
    _file_resource_read(client, api_mapping, resource_definition, **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resources_definitions=resource_definitions_from_file,
    retrieve_mapping=mapping_by_kind,
)
def file_resource_check_status(client,
                               api_mapping,
                               resource_definition,
                               **kwargs):
    _resource_check_status(client, api_mapping, resource_definition, **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resources_definitions=resource_definitions_from_file,
    retrieve_mapping=mapping_by_kind,
)
def file_resource_check_drift(client,
                              api_mapping,
                              resource_definition,
                              **kwargs):
    _resource_check_drift(client, api_mapping, resource_definition, **kwargs)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind,
    resource_state_function=_check_if_resource_exists
)
def resource_update(client, api_mapping, resource_definition, **kwargs):
    result = _resource_update(
        client,
        api_mapping,
        resource_definition,
        **kwargs)
    store_result_for_retrieve_id(result)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data,
)
def custom_resource_update(client, api_mapping, resource_definition, **kwargs):
    response = _do_resource_update(
        client,
        api_mapping,
        resource_definition,
        **kwargs)
    store_result_for_retrieve_id(response)


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind,
    cleanup_runtime_properties=True,  # remove on successful run
    resource_state_function=_check_if_resource_exists
)
def resource_delete(client, api_mapping, resource_definition, **kwargs):
    try:
        read_result = _do_resource_read(
            client, api_mapping, resource_definition, **kwargs)
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

        handle_delete_resource(read_result)
        perform_task = ctx.instance.runtime_properties.get('__perform_task',
                                                           False)

        if perform_task:
            store_result_for_retrieve_id(read_result)
            raise OperationRetry(
                'Delete response: {0}'.format(delete_response))


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_payload,
    retrieve_mapping=mapping_by_kind,
    cleanup_runtime_properties=True,  # remove on successful run
)
def resource_delete_from_payload(client,
                                 api_mapping,
                                 resource_definition,
                                 **kwargs):
    try:
        return _do_resource_delete(
            client, api_mapping, resource_definition, **kwargs)
    except (NonRecoverableError, KuberentesApiOperationError) as e:
        if '(404)' in text_type(e):
            ctx.logger.debug('Ignoring error: {0}'.format(text_type(e)))
        else:
            raise RecoverableError(
                'Raising error: {0}'.format(text_type(e)))


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data,
    cleanup_runtime_properties=True,  # remove on successful run
    resource_state_function=_check_if_resource_exists
)
def custom_resource_delete(client, api_mapping, resource_definition, **kwargs):
    try:
        read_result = _do_resource_read(
            client, api_mapping, resource_definition, **kwargs)
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
        resource_exists = _check_if_resource_exists(
            client, api_mapping, resource_definition, **kwargs)
        handle_delete_resource(resource_exists)
        perform_task = ctx.instance.runtime_properties.get('__perform_task',
                                                           False)

        if perform_task:
            store_result_for_retrieve_id(read_result)
            raise OperationRetry(
                'Delete response: {0}'.format(delete_response))


@with_kubernetes_client
@resource_task(
    retrieve_resources_definitions=resource_definitions_from_file,
    retrieve_mapping=mapping_by_kind,
    cleanup_runtime_properties=True,  # remove on successful run
    resource_state_function=_check_if_resource_exists
)
def file_resource_delete(client, api_mapping, resource_definition, **kwargs):
    _file_resource_delete(client, api_mapping, resource_definition, **kwargs)


def multiple_file_resource_create(**kwargs):
    file_resources = kwargs.get(
        NODE_PROPERTY_FILES,
        ctx.node.properties.get(NODE_PROPERTY_FILES, [])
    )
    validate_file_resources(file_resources)

    for file_resource in file_resources:
        file_resource_create(file=file_resource, **kwargs)


def multiple_file_resource_update(**kwargs):
    file_resources = kwargs.get(
        NODE_PROPERTY_FILES,
        ctx.node.properties.get(NODE_PROPERTY_FILES, [])
    )
    validate_file_resources(file_resources)

    for file_resource in file_resources:
        file_resource_update(file=file_resource, **kwargs)


def multiple_file_resource_check_status(**kwargs):
    file_resources = kwargs.get(
        NODE_PROPERTY_FILES,
        ctx.node.properties.get(NODE_PROPERTY_FILES, [])
    )
    validate_file_resources(file_resources)

    for file_resource in file_resources:
        file_resource_check_status(file=file_resource, **kwargs)


def multiple_file_resource_check_drift(**kwargs):
    file_resources = kwargs.get(
        NODE_PROPERTY_FILES,
        ctx.node.properties.get(NODE_PROPERTY_FILES, [])
    )
    validate_file_resources(file_resources)

    for file_resource in file_resources:
        file_resource_check_drift(file=file_resource, **kwargs)


def multiple_file_resource_read(**kwargs):
    file_resources = kwargs.get(
        NODE_PROPERTY_FILES,
        ctx.node.properties.get(NODE_PROPERTY_FILES, [])
    )
    validate_file_resources(file_resources)

    for file_resource in file_resources:
        file_resource_read(file=file_resource, **kwargs)


def multiple_file_resource_delete(**kwargs):
    file_resources = kwargs.get(
        NODE_PROPERTY_FILES,
        ctx.node.properties.get(NODE_PROPERTY_FILES, [])
    )
    validate_file_resources(file_resources)

    for file_resource in file_resources:
        file_resource_delete(file=file_resource, **kwargs)


@nested_resource_task(
    resources=[
        ('cluster_role_binding', get_cluster_role_binding_payload),
        ('service_account', get_service_account_payload),
    ],
    operation=resource_create_from_payload,
)
def create_token(instance, **_):
    # Create the Token
    sa_resp = instance.runtime_properties['service_account_response']
    secret_payload = get_secret_payload(sa_resp['metadata']['name'])
    try:
        create_resouse_result = resource_create_from_payload(
            payload=secret_payload)
        secret_response = create_resouse_result[0]
    except Exception:
        secret_response = resource_read_from_payload(payload=secret_payload)[0]
    # Store the token, endpoint, and certificate.
    token = secret_response['data']['token']
    certificate = secret_response['data']['ca.crt']
    instance.runtime_properties['secret_response'] = secret_response
    instance.runtime_properties['k8s-service-account-token'] = \
        base64.b64decode(token).decode('utf-8')
    instance.runtime_properties['k8s-ip'] = \
        instance.runtime_properties['capabilities']['endpoint']
    instance.runtime_properties['k8s-cacert'] = \
        base64.b64decode(certificate).decode('utf-8')


@nested_resource_task(
    resources=[
        ('service_account', get_service_account_payload),
        ('cluster_role_binding', get_cluster_role_binding_payload)
    ],
    operation=resource_read_from_payload
)
def read_token(instance, **_):

    # Refresh the Secret details
    sa_resp = instance.runtime_properties['service_account_response']

    secret_payload = get_secret_payload(sa_resp['metadata']['name'])
    secret_response = resource_read_from_payload(payload=secret_payload)[0]

    token = secret_response['data']['token']
    certificate = secret_response['data']['ca.crt']
    instance.runtime_properties['secret_response'] = secret_response

    instance.runtime_properties['k8s-ip'] = \
        instance.runtime_properties['capabilities']['endpoint']
    instance.runtime_properties['k8s-service-account-token'] = \
        base64.b64decode(token).decode('utf-8')
    instance.runtime_properties['k8s-cacert'] = \
        base64.b64decode(certificate).decode('utf-8')


@nested_resource_task(
    resources=[
        ('service_account', get_service_account_payload),
        ('cluster_role_binding', get_cluster_role_binding_payload)
    ],
    operation=resource_read_from_payload
)
def get_token_status(instance, **_):

    # Refresh the Secret details
    sa_resp = instance.runtime_properties['service_account_response']

    secret_payload = get_secret_payload(sa_resp['metadata']['name'])
    secret_response = resource_read_from_payload(payload=secret_payload)[0]

    if secret_response:
        ctx.logger.info('Status: True')


@nested_resource_task(
    nested_ops_first=False,
    resources=[
        ('service_account', get_service_account_payload),
        ('cluster_role_binding', get_cluster_role_binding_payload)
    ],
    operation=resource_delete_from_payload,
)
def delete_token(instance, **_):

    # Delete the secret.
    sa_resp = instance.runtime_properties['service_account_response']
    secret_payload = get_secret_payload(sa_resp['metadata']['name'])
    resource_delete_from_payload(
        payload=secret_payload,
        resource_id='{}-token'.format(sa_resp['metadata']['name']))
    if 'k8s-service-account-token' in instance.runtime_properties:
        del instance.runtime_properties['k8s-service-account-token']
    if 'k8s-cacert' in instance.runtime_properties:
        del instance.runtime_properties['k8s-cacert']


def prepare_pvc_delete(resource_definition, client, api_mapping, kwargs):
    metadata = deepcopy(resource_definition.metadata)
    metadata['finalizers'] = None
    resource_definition = KubernetesResourceDefinition(
        kind=resource_definition.kind,
        apiVersion=resource_definition.api_version,
        metadata=metadata
    )
    try:
        _do_resource_update(
            client,
            api_mapping,
            resource_definition,
            **kwargs
        )
    except KuberentesApiOperationError:
        return
