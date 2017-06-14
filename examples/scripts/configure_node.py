#!/usr/bin/env python

import subprocess
from cloudify import ctx
from cloudify.state import ctx_parameters as inputs

START_COMMAND = 'sudo kubeadm join --token {0} {1}:{2}'


def execute_command(_command):

    ctx.logger.debug('_command {0}.'.format(_command))

    subprocess_args = {
        'args': _command.split(),
        'stdout': subprocess.PIPE,
        'stderr': subprocess.PIPE
    }

    ctx.logger.debug('subprocess_args {0}.'.format(subprocess_args))

    process = subprocess.Popen(**subprocess_args)
    output, error = process.communicate()

    ctx.logger.debug('command: {0} '.format(_command))
    ctx.logger.debug('output: {0} '.format(output))
    ctx.logger.debug('error: {0} '.format(error))
    ctx.logger.debug('process.returncode: {0} '.format(process.returncode))

    if process.returncode:
        ctx.logger.error('Running `{0}` returns error.'.format(_command))
        return False

    return output


if __name__ == '__main__':

    # masters = [x for x in ctx.instance.relationships
    #            if 'cloudify.nodes.Kubernetes.Master' in
    #               x.target.node.type_hierarchy]
    # ctx_master = masters[0]
    # join_command = (inputs.get('join_command')
    #                 or ctx_master.target.instance.runtime_properties[
    #                    'join_command']
    join_command = inputs.get('join_command')
    join_command = 'sudo {0} --skip-preflight-checks'.format(join_command)
    execute_command(join_command)
