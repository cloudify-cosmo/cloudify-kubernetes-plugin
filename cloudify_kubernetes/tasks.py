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

# hack for import namespaced modules
import cloudify_importer  # noqa

from cloudify import ctx
from cloudify.exceptions import (
    OperationRetry,
    RecoverableError)

from k8s.exceptions import KuberentesApiOperationError
from k8s import status_mapping
from .decorators import (resource_task,
                         with_kubernetes_client,
                         INSTANCE_RUNTIME_PROPERTY_KUBERNETES)
from .utils import (mapping_by_data,
                    mapping_by_kind,
                    retrieve_path,
                    resource_definition_from_blueprint,
                    resource_definitions_from_file)


DEFAULT_NAMESPACE = 'default'
NODE_PROPERTY_FILES = 'files'
NODE_PROPERTY_OPTIONS = 'options'


def _retrieve_id(resource_instance, file=None):
    data = resource_instance.runtime_properties[
        INSTANCE_RUNTIME_PROPERTY_KUBERNETES
    ]

    if isinstance(data, dict) and file:
        data = data[file]

    return data['metadata']['name']


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
                    isinstance(v, str) and not \
                    isinstance(v, unicode):
                resource[k] = str(v)

    def _cleanuped_dict(self, resource):
        for k in resource:
            if not resource[k]:
                continue
            if isinstance(resource[k], list):
                self._cleanuped_list(resource[k])
            elif isinstance(resource[k], dict):
                self._cleanuped_dict(resource[k])
            elif not isinstance(resource[k], int) and not \
                    isinstance(resource[k], str) and not \
                    isinstance(resource[k], unicode):
                resource[k] = str(resource[k])

    def to_dict(self):
        return self.value


def _do_resource_create(client, api_mapping, resource_definition, **kwargs):
    if 'namespace' not in kwargs:
        kwargs['namespace'] = DEFAULT_NAMESPACE

    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    ctx.logger.debug('Node options {0}'.format(options))
    if ctx.node.properties.get('use_external_resource'):
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

    if ctx.node.properties.get('use_external_resource'):
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

        if not ctx.node.properties.get('use_external_resource'):
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
        _retrieve_id(ctx.instance, path),
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
