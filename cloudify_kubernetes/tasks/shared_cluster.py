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

from .._compat import PY2, PY311
from ..utils import (get_node,
                     get_instance,
                     with_rest_client,
                     execute_workflow,
                     get_kubernetes_cluster_node_instance_id)

try:
    from cloudify_types.component.polling import (
        poll_with_timeout,
        verify_execution_state,
        is_all_executions_finished)
    from cloudify_types.shared_resource.constants import \
        WORKFLOW_EXECUTION_TIMEOUT
except ImportError:
    if PY311:
        from mgmtworker.cloudify_types.polling import poll_with_timeout
        from mgmtworker.cloudify_types.component.polling import (
            verify_execution_state,
            is_all_executions_finished)
        from mgmtworker.cloudify_types.shared_resource.constants import \
            WORKFLOW_EXECUTION_TIMEOUT
    elif not PY2:
        raise


@with_rest_client
def refresh_config(rest_client, **_):
    """cfy_extensions.cloudify_types.shared_resource.execute_workflow"""
    node = get_node(ctx)
    try:
        deployment_id = node.properties['resource_config']['deployment']['id']
    except KeyError:
        raise NonRecoverableError(
            'A deployment ID for the shared resource was not provided.')
    node_instance = get_kubernetes_cluster_node_instance_id(deployment_id)

    if not poll_with_timeout(
            lambda: is_all_executions_finished(rest_client, deployment_id),
            timeout=WORKFLOW_EXECUTION_TIMEOUT,
            expected_result=True):
        return ctx.operation.retry(
            'The "{0}" deployment is not ready for workflow execution.'.format(
                deployment_id))

    execution = execute_workflow(
        deployment_id,
        'execute_operation',
        {
            'operation': 'cloudify.interfaces.lifecycle.poststart',
            'node_instance_ids': [node_instance]
        })
    if not verify_execution_state(
            client=rest_client,
            execution_id=execution['id'],
            deployment_id=deployment_id,
            timeout=WORKFLOW_EXECUTION_TIMEOUT,
            redirect_log=True,
            workflow_state='terminated',
            instance_ctx=get_instance(ctx)):
        raise NonRecoverableError(
            'Execution "{0}" failed for "{1}" deployment.'.format(
                execution['id'], deployment_id))
