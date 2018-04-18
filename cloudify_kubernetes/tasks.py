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

# hack for import namespaced modules
import cloudify_importer # noqa

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
            elif (not isinstance(v, int) and  # integer and bool
                  not isinstance(v, str) and
                  not isinstance(v, unicode)):
                resource[k] = str(v)

    def _cleanuped_dict(self, resource):
        for k in resource:
            if not resource[k]:
                continue
            if isinstance(resource[k], list):
                self._cleanuped_list(resource[k])
            elif isinstance(resource[k], dict):
                self._cleanuped_dict(resource[k])
            elif (not isinstance(resource[k], int) and  # integer and bool
                  not isinstance(resource[k], str) and
                  not isinstance(resource[k], unicode)):
                resource[k] = str(resource[k])

    def to_dict(self):
        return self.value


def _do_resource_create(client, api_mapping, resource_definition, **kwargs):
    if 'namespace' not in kwargs:
        kwargs['namespace'] = DEFAULT_NAMESPACE

    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    ctx.logger.debug('Node options {0}'.format(options))
    return JsonCleanuper(client.create_resource(
        api_mapping,
        resource_definition,
        options
    )).to_dict()


def _do_resource_read(client, api_mapping, id, **kwargs):
    if 'namespace' not in kwargs:
        kwargs['namespace'] = DEFAULT_NAMESPACE

    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    ctx.logger.debug('Node options {0}'.format(options))
    return JsonCleanuper(client.read_resource(
        api_mapping,
        id,
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

    if resource_kind == "Pod":
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

    elif resource_kind == "Service":
        status = response.get('status')
        load_balancer = status.get('load_balancer')
        if response.get('spec', {}).get('type', '') == 'Ingress' and \
                load_balancer and load_balancer.get('ingress') is None:
            raise OperationRetry(
                'status {0} in phase {1}'.format(
                    status,
                    [{'load_balancer': {'ingress': None}}]))
        else:
            ctx.logger.debug('status {0}'.format(status))

    elif resource_kind == 'Deployment':
        conditions = response['status']['conditions']
        if isinstance(conditions, list):
            for condition in conditions:
                if condition['type'] == 'Available':
                    ctx.logger.debug('Deployment condition is Available')

                elif condition['type'] == 'ReplicaFailure':
                    raise NonRecoverableError(
                        'Deployment condition is ReplicaFailure ,'
                        'reason:{0}, message: {1}'
                        ''.format(condition['reason'], condition['message']))

                elif condition['type'] == 'Progressing' and \
                        condition['reason'] != 'NewReplicaSetAvailable':
                    raise OperationRetry(
                        'Deployment condition is Progressing')
        else:
            raise OperationRetry('Deployment condition is not ready yet')

    elif resource_kind == 'PersistentVolumeClaim':
        status = response['status']['phase']
        if status in ['Pending', 'Available', 'Bound']:
            ctx.logger.debug('PersistentVolumeClaim status is Bound')

        else:
            raise OperationRetry(
                'Unknown PersistentVolume status {0}'.format(status))

    elif resource_kind == 'PersistentVolume':
        status = response['status']['phase']
        if status in ['Bound', 'Available']:
            ctx.logger.debug('PersistentVolume status is {0}'.format(status))

        else:
            raise OperationRetry(
                'Unknown PersistentVolume status {0}'.format(status))

    elif resource_kind in ['ReplicaSet', 'ReplicationController']:
        ready_replicas = response['status'].get('ready_replicas')
        replicas = response['status'].get('replicas')

        if ready_replicas is None:
            raise OperationRetry(
                '{0} status not ready yet'.format(resource_kind))

        elif ready_replicas != replicas:
            raise OperationRetry(
                'Only {0} of {1} replicas are ready'.format(
                    ready_replicas, replicas))

        elif ready_replicas == replicas:
            ctx.logger.debug('All {0} replicas are ready now'.format(replicas))


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

    return JsonCleanuper(client.delete_resource(
        api_mapping,
        resource_definition,
        resource_id,
        options,
    )).to_dict()


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
    retrieve_mapping=mapping_by_kind
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
            'Delete response: {0}'.format(delete_response))


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
    retrieve_mapping=mapping_by_data
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

        raise OperationRetry(
            'Delete response: {0}'.format(delete_response))


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
        resource_definition,
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
