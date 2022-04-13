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

import ast
import json

from cloudify.workflows import ctx
from cloudify.decorators import workflow
from cloudify.manager import get_rest_client
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError

from . import utils

POSTSTART = 'cloudify.interfaces.lifecycle.poststart'
UPDATE = 'cloudify.interfaces.lifecycle.update'
CHECKDRIFT = 'cloudify.interfaces.lifecycle.check_drift'
DELETE = 'cloudify.interfaces.lifecycle.delete'
CREATE = 'cloudify.interfaces.lifecycle.create'


def execute_node_instance_operation(_node_instance,
                                    _operation,
                                    _params=None):
    """
    Handles sending events and executing operations.

    :param _node_instance: A NodeInstance object from cloudify.manager.
    :param _operation: A string with the name of the workflow operation.
    :param _params: Optional parameters to the workflow operation.
    """

    # Prepare the kwargs to the execute_operation method.
    _params = _params or {}
    operation_args = {
        'operation': _operation,
    }
    if _params:
        operation_args['kwargs'] = _params

    graph = ctx.graph_mode()
    sequence = graph.sequence()
    sequence.add(
        _node_instance.send_event(
            'Starting to run operation: {0}'.format(operation_args)),
        _node_instance.execute_operation(**operation_args),
        _node_instance.send_event(
            'Finished running operation: {0}'.format(operation_args))
    )
    return graph.execute()


@workflow
def update_resource_definition(node_instance_id,
                               resource_definition_changes,
                               **_):
    """
    Updates a Kubernetes Resource's resource definition.

    Example Usage:
    ```shell
    $ cfy blueprints upload \
        examples/wordpress-blueprint.yaml -b wordpress
    $ cfy deployments create --skip-plugins-validation -b wordpress
    $ cfy executions start install -d wordpress
    $ cfy node-instances list -d wordpress
    # At this point copy the node_instance_id of wordpress_svc node.
    $ cfy node-instances get [wordpress_svc node instance id]
    # At this point copy the cluster_ip in the resource definition.
    $ cfy executions start update_resource_definition -d wordpress -vv \
        -p resource_definition_changes="
        {'metadata': {'resourceVersion': '0'},
        'spec': {'clusterIP': '10.110.97.242',
        'ports': [{'port': 80, 'nodePort': 30081}]}
        }" -p node_instance_id=[wordpress_svc node instance id]
    ```

    :param node_instance_id: A string.
        The node instance ID of the node instance containing the resource.
    :param resource_definition_changes: A dictionary encoded as a unicode
        string representing the changes to the resoruce definition.
    """

    try:
        resource_definition_changes = \
            json.loads(resource_definition_changes)
    except json.JSONDecodeError as e:

        if 'Key name must be string at char' in str(e):
            resource_definition_changes = \
                ast.literal_eval(resource_definition_changes)
        elif 'Unexpected' in str(e):
            resource_definition_changes = \
                utils.resource_definitions_from_file_result(
                    resource_definition_changes)

    node_instance = ctx.get_node_instance(node_instance_id)

    if not node_instance_id:
        raise NonRecoverableError(
            'No such node_instance_id in deployment: {0}.'.format(
                node_instance_id))

    # Execute start operation to update to
    # the latest version of the resource definition.
    node_instance.logger.info(
        'Executing start in order to get the current state.')
    execute_node_instance_operation(node_instance, POSTSTART)
    node_instance.logger.info(
        'Executed start in order to get the current state.')

    # Execute update operation to push the change to Kubernetes.
    node_instance.logger.info(
        'Executing update in order to push the new changes.')
    execute_node_instance_operation(
        node_instance,
        UPDATE,
        _params={utils.DEFINITION_ADDITIONS: resource_definition_changes})
    node_instance.logger.info(
        'Executed update in order to push the new changes.')


def refresh_and_store_token(ctx,
                            kubernetes_cluster_node_instance_id,
                            deployment_capability_name,
                            service_account_node_instance_id,
                            secret_token_node_instance_id,
                            store_token_and_kubeconfig_id):

    cluster_ni = lookup_node_instance(
        kubernetes_cluster_node_instance_id)
    execute_node_instance_operation(cluster_ni, POSTSTART)
    execute_node_instance_operation(cluster_ni, CHECKDRIFT)

    create_secrets_kubernetes_config(deployment_capability_name)

    service_account_ni = lookup_node_instance(service_account_node_instance_id)
    execute_node_instance_operation(service_account_ni, UPDATE)
    execute_node_instance_operation(service_account_ni, POSTSTART)

    secret_token_ni = lookup_node_instance(secret_token_node_instance_id)
    execute_node_instance_operation(secret_token_ni, DELETE)
    execute_node_instance_operation(secret_token_ni, CREATE)

    store_token_and_kubeconfig_ni = lookup_node_instance(
        store_token_and_kubeconfig_id)
    execute_node_instance_operation(store_token_and_kubeconfig_ni, CREATE)


def create_secrets_kubernetes_config(deployment_capability_name):
    client = get_rest_client()

    capabilities = client.deployments.capabilities. \
        get(ctx.deployment.id).get('capabilities', {})
    kubernetes_config = capabilities.get(deployment_capability_name, {}) \
        .get('file_content', {})
    ctx.logger.info('This is the capability: {}'.format(kubernetes_config))

    try:
        client.secrets.create('kubernetes_config', str(kubernetes_config))
    except CloudifyClientError as err:
        ctx.logger.error('{}'.format(str(err)))


def lookup_node_instance(provided_node_instance_id):
    try:
        desired_node_instance = ctx.get_node_instance(
            provided_node_instance_id)

    except RuntimeError:
        desired_node_instance = None
        for node_instance in ctx.node_instances:
            if node_instance.node_id == provided_node_instance_id:
                desired_node_instance = node_instance
                break
    if not desired_node_instance:
        raise NonRecoverableError(
            'A valid node instance or node ID for a '
            'X node was not found'
        )
    return desired_node_instance
