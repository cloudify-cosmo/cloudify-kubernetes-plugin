#!/usr/bin/env python
#
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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
#

from cloudify.manager import get_rest_client
from fabric.api import run

command = "kubectl -n default describe secret " \
          "$(kubectl -n default get secret | " \
          "grep {0} | awk '{{print $1}}') " \
          "| grep 'token:' | awk '{{print $2}}'"


def get_token(service_account_name):
    token = run(command.format(service_account_name))
    client = get_rest_client()
    client.secrets.create(key=service_account_name, value=token)
