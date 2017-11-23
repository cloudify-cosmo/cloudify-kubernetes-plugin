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


from cloudify import ctx
from cloudify.exceptions import (
    NonRecoverableError,
    OperationRetry,
    RecoverableError)

from k8s.exceptions import KuberentesApiOperationError
from .decorators import (resource_task,
                         with_kubernetes_client)
from .utils import (mapping_by_data,
                    mapping_by_kind,
                    resource_definition_from_blueprint,
                    resource_definition_from_file)


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


def _do_resource_create(client, api_mapping, resource_definition, **kwargs):
    if 'namespace' not in kwargs:
        kwargs['namespace'] = DEFAULT_NAMESPACE

    return client.create_resource(
        api_mapping,
        resource_definition,
        ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    ).to_dict()


def _do_resource_read(client, api_mapping, id, **kwargs):
    if 'namespace' not in kwargs:
        kwargs['namespace'] = DEFAULT_NAMESPACE

    return client.read_resource(
        api_mapping,
        id,
        ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    ).to_dict()


def _do_resource_delete(client, api_mapping, id, **kwargs):
    if 'namespace' not in kwargs:
        kwargs['namespace'] = DEFAULT_NAMESPACE

    return client.delete_resource(
        api_mapping,
        id,
        ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    ).to_dict()


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

    lifecycle = ctx.node.properties.get('lifecycle', {})
    if not isinstance(lifecycle, dict):
        return

    response_path_map = lifecycle.get('response_path', '')
    if not isinstance(response_path_map, basestring):
        return

    response_path = response_path_map.split('.')
    if len(response_path) == 1 and response_path[0] == '':
        return

    logic = lifecycle.get('logic')
    if not isinstance(logic, dict):
        return

    fail_logic = logic.get('fail')
    poll_logic = logic.get('poll')
    pass_logic = logic.get('pass')
    if not fail_logic or not poll_logic or not pass_logic:
        return

    read_response = _do_resource_read(
        client,
        api_mapping,
        _retrieve_id(ctx.instance),
        **kwargs
    )

    ctx.instance.runtime_properties[INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = \
        read_response

    response_path_type = lifecycle.get('response_path_type', {})
    if isinstance(response_path_type, dict):
        current_state = read_response
        for level in response_path:
            current_state = current_state[level]
        message = '{0} in {1}'
        if current_state in fail_logic:
            raise NonRecoverableError(
                message.format(current_state, fail_logic))
        elif current_state in poll_logic:
            raise OperationRetry(
                message.format(current_state, poll_logic))
        elif current_state in pass_logic:
            ctx.logger.debug(
                message.format(current_state, pass_logic))

    return


@with_kubernetes_client
@resource_task(
    retrieve_resource_definition=resource_definition_from_blueprint,
    retrieve_mapping=mapping_by_kind
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
