#!/usr/bin/env python

import subprocess
from cloudify import ctx
from cloudify.exceptions import RecoverableError


def check_for_docker():

    command = 'docker ps'

    try:
        process = subprocess.Popen(
            command.split()
        )
    except OSError:
        return False

    output, error = process.communicate()

    ctx.logger.debug('command: {0} '.format(command))
    ctx.logger.debug('output: {0} '.format(output))
    ctx.logger.debug('error: {0} '.format(error))
    ctx.logger.debug('process.returncode: {0} '.format(process.returncode))

    if process.returncode:
        ctx.logger.error('Running `{0}` returns error.'.format(command))
        return False

    return True


if __name__ == '__main__':

    if not check_for_docker():
        raise RecoverableError('Waiting for docker to be installed.')
