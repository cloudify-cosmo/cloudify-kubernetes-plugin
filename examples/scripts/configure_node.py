#!/usr/bin/env python
#
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

import subprocess
from cloudify import ctx
from cloudify.state import ctx_parameters as inputs


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

    join_command = inputs['join_command']
    join_command = 'sudo {0} --skip-preflight-checks'.format(join_command)
    execute_command(join_command)

    # Install weave-related utils
    execute_command('sudo curl -L git.io/weave -o /usr/local/bin/weave')
    execute_command('sudo chmod a+x /usr/local/bin/weave')
    execute_command('sudo curl -L git.io/scope -o /usr/local/bin/scope')
    execute_command('sudo chmod a+x /usr/local/bin/scope')
    execute_command('/usr/local/bin/scope launch')

    hostname = execute_command('hostname')
    ctx.instance.runtime_properties['hostname'] = hostname.rstrip('\n')
