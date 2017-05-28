from cloudify.decorators import workflow
from cloudify.exceptions import NonRecoverableError
from cloudify.workflows import ctx

from fabric.api import env, run, settings
import json
import re


FORBIDDEN_CHARACTERS = '$!&`|><;#{}()'

AGENT_CONFIG_PROPERTY = 'agent_config'
AGENT_CONFIG_USER_PROPERTY = 'user'
AGENT_CONFIG_KEY_PROPERTY = 'key'
IP_PROPERTY = 'ip'


def _retrieve_ssh_credentials(node):
    if not node:
        raise NonRecoverableError('Cannot retrieve SSH credentials - node not found')

    try:
        return {
            'ssh_host': node.properties[IP_PROPERTY],
            'ssh_user': node.properties[AGENT_CONFIG_PROPERTY][AGENT_CONFIG_USER_PROPERTY],
            'ssh_keyfile': node.properties[AGENT_CONFIG_PROPERTY][AGENT_CONFIG_KEY_PROPERTY]
        }
    except KeyError as e:
        raise NonRecoverableError(
            'Cannot retrieve SSH credentials - one or more of required parameters is not specified. Details {0}'
            .format(str(e)))


def _prepare_fabric_env(ssh_host, ssh_user, ssh_keyfile):
    env['host_string'] = '{0}@{1}'.format(ssh_user, ssh_host)
    env['key_filename'] = ssh_keyfile


def _prepare_kubectl_command(arguments):
    ctx.logger.debug('Input kubectl arguments: {0}'.format(arguments))

    command = 'kubectl {0}'.format(re.sub('[{0}]'.format(FORBIDDEN_CHARACTERS), '', arguments.replace('kubectl', '')))
    ctx.logger.debug('Kubectl command "{0}" will be executed'.format(command))

    return command


def _run_command(command, json_result=False):
    if json_result:
        command = '{0} -o json'.format(command)

    ctx.logger.debug('Executing command "{0}" ...'.format(command))

    with settings(warn_only=True):
        result = run(command)
        ctx.logger.debug('Command execution result: {0}'.format(result))

        return {
            'successful': result.return_code == 0,
            'data_type': 'json' if json_result else 'text',
            'data': (json.loads(result) if json_result else result) if result.return_code == 0 else '',
            'error': result if not result.return_code == 0 else '',
            'return_code': result.return_code
        }


@workflow
def execute_kubectl_command(kubectl_arguments, kubectl_node_name, **kwargs):
    node = ctx.get_node(kubectl_node_name)

    _prepare_fabric_env(**_retrieve_ssh_credentials(node))
    command = _prepare_kubectl_command(kubectl_arguments)
    result = _run_command(command, True)

    if not result['successful']:
        result = _run_command(command, False)

    result_json = json.dumps(result)

    ctx.logger.info('Workflow execution result: {0}'.format(result_json))

    return result_json
