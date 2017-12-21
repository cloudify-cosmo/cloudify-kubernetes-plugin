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


from cloudify import ctx
from datetime import datetime
from cloudify.exceptions import (
    NonRecoverableError,
    OperationRetry,
    RecoverableError)

from .loader import register_callback
register_callback()

from k8s.exceptions import KuberentesApiOperationError
from .decorators import (resource_task,
                         with_kubernetes_client)
from .utils import (mapping_by_data,
                    mapping_by_kind,
                    resource_definition_from_blueprint,
                    resource_definition_from_file,)


DEFAULT_NAMESPACE = 'default'
INSTANCE_RUNTIME_PROPERTY_KUBERNETES = 'kubernetes'
NODE_PROPERTY_FILE = 'file'
NODE_PROPERTY_FILE_RESOURCE_PATH = 'resource_path'
NODE_PROPERTY_FILES = 'files'
NODE_PROPERTY_OPTIONS = 'options'


def _retrieve_id(resource_instance, file=None):
    data = resource_instance.runtime_properties[
        INSTANCE_RUNTIME_PROPERTY_KUBERNETES
    ]

    if isinstance(data, dict) and file:
        data = data[file]

    return data['metadata']['name']


def _retrieve_path(kwargs):
    return kwargs\
        .get(NODE_PROPERTY_FILE, {})\
        .get(NODE_PROPERTY_FILE_RESOURCE_PATH, '')


def _cleanuped_list(resource):
    for k, v in enumerate(resource):
        if isinstance(v, list):
            _cleanuped_list(v)
        elif isinstance(v, dict):
            _cleanuped_dict(v)
        elif isinstance(v, datetime):
            resource[k] = str(v)


def _cleanuped_dict(resource):
    for k in resource:
        if isinstance(resource[k], list):
            _cleanuped_list(resource[k])
        elif isinstance(resource[k], dict):
            _cleanuped_dict(resource[k])
        elif isinstance(resource[k], datetime):
            resource[k] = str(resource[k])


def _cleanuped(resource):
    if isinstance(resource, list):
        _cleanuped_list(resource)
    elif isinstance(resource, dict):
        _cleanuped_dict(resource)
    return resource


def _do_resource_create(client, api_mapping, resource_definition, **kwargs):
    if 'namespace' not in kwargs:
        kwargs['namespace'] = DEFAULT_NAMESPACE

    return _cleanuped(client.create_resource(
        api_mapping,
        resource_definition,
        ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    ).to_dict())


def _do_resource_read(client, api_mapping, id, **kwargs):
    if 'namespace' not in kwargs:
        kwargs['namespace'] = DEFAULT_NAMESPACE

    return _cleanuped(client.read_resource(
        api_mapping,
        id,
        ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    ).to_dict())


def _do_resource_status_check(resource_kind, response):

    if "Pod" == resource_kind:
        status = response['status']['phase']
        if status in ['Failed']:
            raise NonRecoverableError(
                'status {0} in phase {1}'.format(
                    status, ['Failed']))
        elif status in ['Pending', 'Unknown']:
            raise OperationRetry(
                'status {0} in phase {1}'.format(
                    status, ['Pending', 'Unknown']))
        elif status in ['Running', 'Succeeded']:
            ctx.logger.debug(
                'status {0} in phase {1}'.format(
                    status, ['Running', 'Succeeded']))

    elif "Service" in resource_kind:
        status = response['status']
        if status in [{'load_balancer': {'ingress': None}}]:
            raise OperationRetry(
                'status {0} in phase {1}'.format(
                    status,
                    [{'load_balancer': {'ingress': None}}]))
        else:
            ctx.logger.debug('status {0}'.format(status))


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

    return _cleanuped(client.delete_resource(
        api_mapping,
        resource_definition,
        resource_id,
        options,
    ).to_dict())


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind
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
    retrieve_mapping=mapping_by_kind
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

        raise OperationRetry(
            'Delete respone: {0}'.format(delete_response))


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_data
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
    retrieve_mapping=mapping_by_data
)
def custom_resource_delete(client, api_mapping, resource_definition, **kwargs):
    _do_resource_delete(
        client,
        api_mapping,
        _retrieve_id(ctx.instance),
        **kwargs
    )


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_file,
    retrieve_mapping=mapping_by_kind
)
def file_resource_create(client, api_mapping, resource_definition, **kwargs):
    result = _do_resource_create(
        client,
        api_mapping,
        resource_definition,
        **kwargs
    )

    if INSTANCE_RUNTIME_PROPERTY_KUBERNETES in \
            ctx.instance.runtime_properties:

        if isinstance(
            ctx.instance.runtime_properties[
                INSTANCE_RUNTIME_PROPERTY_KUBERNETES
            ],
            dict
        ):
            path = _retrieve_path(kwargs)

            ctx.instance.runtime_properties[
                INSTANCE_RUNTIME_PROPERTY_KUBERNETES
            ][path] = result

            return

    else:
        ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES]\
            = result


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_file,
    retrieve_mapping=mapping_by_kind
)
def file_resource_delete(client, api_mapping, resource_definition, **kwargs):
    path = _retrieve_path(kwargs)

    _do_resource_delete(
        client,
        api_mapping,
        _retrieve_id(ctx.instance, path),
        **kwargs
    )


def multiple_file_resource_create(**kwargs):
    ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES]\
        = {}

    file_resources = kwargs.get(
        NODE_PROPERTY_FILES,
        ctx.node.properties.get(NODE_PROPERTY_FILES, [])
    )

    for file_resource in file_resources:
        file_resource_create(file=file_resource, **kwargs)


def multiple_file_resource_delete(**kwargs):
    file_resources = kwargs.get(
        NODE_PROPERTY_FILES,
        ctx.node.properties.get(NODE_PROPERTY_FILES, [])
    )

    for file_resource in file_resources:
        file_resource_delete(file=file_resource, **kwargs)
