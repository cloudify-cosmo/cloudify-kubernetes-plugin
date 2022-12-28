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
from cloudify.exceptions import NonRecoverableError

from ..k8s import status_mapping
from ..k8s.exceptions import KuberentesApiOperationError
from ..utils import (set_namespace,
                     JsonCleanuper,
                     PERMIT_REDEFINE,
                     set_custom_resource,
                     NODE_PROPERTY_OPTIONS,
                     handle_delete_resource)


def _do_resource_create(client, api_mapping, resource_definition, **kwargs):
    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    set_namespace(kwargs, resource_definition)
    set_custom_resource(options, resource_definition)
    perform_task = ctx.instance.runtime_properties.get('__perform_task', False)
    if not perform_task:
        return _do_resource_read(
            client, api_mapping, resource_definition, **kwargs)
    return JsonCleanuper(client.create_resource(
        api_mapping,
        resource_definition,
        options)).to_dict()


def _do_resource_read(client, api_mapping, resource_definition, **kwargs):
    if not resource_definition:
        raise NonRecoverableError(
            'No resource was found in runtime properties for reading. '
            'This can occur when the node property {0} is True, and '
            'resources were created and deleted out of order.'.format(
                PERMIT_REDEFINE)
        )
    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    set_namespace(kwargs, resource_definition)
    set_custom_resource(options, resource_definition)
    return JsonCleanuper(client.read_resource(
        api_mapping,
        resource_definition,
        options
    )).to_dict()


def _do_resource_update(client, api_mapping, resource_definition, **kwargs):
    options = ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    set_namespace(kwargs, resource_definition)
    set_custom_resource(options, resource_definition)

    return JsonCleanuper(client.update_resource(
        api_mapping,
        resource_definition,
        ctx.node.properties.get(NODE_PROPERTY_OPTIONS, kwargs)
    )).to_dict()


def _do_resource_status_check(resource_kind, response):
    """ If this returns NoneType, then check_status is not supported.
        If this returns Boolean, then check status is supported and
        we return the readiness
    """
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
    set_namespace(kwargs, resource_definition)
    set_custom_resource(options, resource_definition)

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

    resource_exists = _check_if_resource_exists(
        client, api_mapping, resource_definition, **kwargs)
    handle_delete_resource(resource_exists)
    perform_task = ctx.instance.runtime_properties.get('__perform_task', False)
    if not perform_task:
        return JsonCleanuper(resource_exists).to_dict()
    return JsonCleanuper(client.delete_resource(
        api_mapping,
        resource_definition,
        resource_id,
        options,
    )).to_dict()


def _check_if_resource_exists(client,
                              api_mapping,
                              resource_definition,
                              **kwargs):
    try:
        return _do_resource_read(
            client, api_mapping, resource_definition, **kwargs)
    except KuberentesApiOperationError:
        ctx.logger.error('The resource {0} was not found.'.format(
            resource_definition.metadata['name']))
        return
