########
# Copyright (c) 2014-2019 Cloudify Platform Ltd. All rights reserved
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

import os
import json
import base64
from os import environ
from contextlib import contextmanager

import pytest

from ecosystem_tests.dorkl import cleanup_on_failure
from ecosystem_tests.dorkl.commands import handle_process
from ecosystem_tests.dorkl.cloudify_api import (
    cloudify_exec,
    blueprints_upload,
    deployments_create,
    executions_start)

TEST_ID = environ.get('__ECOSYSTEM_TEST_ID', 'plugin-examples')


@contextmanager
def test_cleaner_upper(test_id):
    try:
        yield
    except Exception:
        cleanup_on_failure(test_id)
        raise


@pytest.mark.dependency()
def test_update(*_, **__):
    deployment_id = TEST_ID + '-update'
    setup_cli()
    with test_cleaner_upper(deployment_id):
        try:
            # Upload Cloud Watch Blueprint
            blueprints_upload(
                'examples/file-test.yaml',
                deployment_id)
            # Create Cloud Watch Deployment with Instance ID input
            deployments_create(
                deployment_id, {"resource_path": "resources/pod.yaml"})
            # Install Cloud Watch Deployment
            executions_start('install', deployment_id)
            after_install = get_pod_info()
            executions_start(
                'update_resource_definition',
                deployment_id,
                params={
                    'resource_definition_changes': {
                        {
                            "kind": "Pod",
                            "metadata": {
                                "name": "nginx-test-pod"
                            },
                            "spec": {
                                "containers": [
                                    {
                                        "name": "nginx-test-pod",
                                        "image": "nginx:latest"
                                    }
                                ]
                            }
                        }
                    }
                }
            )
            after_update = get_pod_info()
            assert after_install[0]['image'] == 'nginx:stable'
            assert after_update[0]['image'] == 'nginx:latest'
            # Uninstall Cloud Watch Deployment
            executions_start('uninstall', deployment_id)
        except:
            cleanup_on_failure(deployment_id)


def setup_cli():
    cluster_name = "kube-{}-cluster".format(os.environ['CIRCLE_BUILD_NUM'])
    capabilities = cloudify_exec('cfy deployments capabilities gcp-gke')
    cloudify_exec('cfy secrets create -s {} kubernetes_endpoint'.format(
        capabilities['endpoint']['value']))
    with open('gcp.json', 'wb') as outfile:
        creds = base64.b64decode(os.environ['gcp_credentials'])
        outfile.write(creds)
    handle_process('gcloud auth activate-service-account --key-file gcp.json')
    handle_process(
        'gcloud container clusters get-credentials {} --region us-west1-a'
        .format(cluster_name))


def get_pod_info():
    return json.loads(
        handle_process('kubectl get pod nginx-test-pod --output="json"'))
