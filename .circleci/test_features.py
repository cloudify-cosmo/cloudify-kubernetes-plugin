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
import yaml
import base64
import tempfile
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


@pytest.mark.dependency()
def test_update(*_, **__):
    deployment_id = TEST_ID + '-update'
    setup_cli()
    try:
        # Upload Cloud Watch Blueprint
        blueprints_upload(
            'examples/file-test.yaml',
            deployment_id)
        # Create Cloud Watch Deployment with Instance ID input
        deployments_create(
            deployment_id, {"resource_path": "resources/pod.yaml"})
        # Install Cloud Watch Deployment
        executions_start('install', deployment_id, 300)
        after_install = get_pod_info()
        update_params = {
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
        params = {'resource_definition_changes': update_params}
        tmp = tempfile.NamedTemporaryFile(delete=false, mode='w', suffix='.yaml')
        yaml.dump(params, tmp)
        tmp.close()
        executions_start(
            'update_resource_definition',
            deployment_id,
            300,
            params=tmp
        )
        os.remove(tmp.name)
        after_update = get_pod_info()
        assert after_install['spec']['containers'][0]['image'] == 'nginx:stable'
        assert after_update['spec']['containers'][0]['image'] == 'nginx:latest'
        # Uninstall Cloud Watch Deployment
        executions_start('uninstall', deployment_id, 300)
    except:
        cleanup_on_failure(deployment_id)


def setup_cli():
    cluster_name = runtime_properties(
        node_instance_by_name('kubernetes-cluster')['id'])['name']
    capabilities = cloudify_exec('cfy deployments capabilities gcp-gke')
    cloudify_exec('cfy secrets create -u -s {} kubernetes_endpoint'.format(
        capabilities['endpoint']['value']), get_json=False)
    with open('gcp.json', 'wb') as outfile:
        creds = base64.b64decode(os.environ['gcp_credentials'])
        outfile.write(creds)
    handle_process('gcloud auth activate-service-account --key-file gcp.json')
    handle_process(
        'gcloud container clusters get-credentials {} --region us-west1-a'
        .format(cluster_name))


def get_pod_info():
    cluster_name = runtime_properties(
        node_instance_by_name('kubernetes-cluster')['id'])['name']
    handle_process(
        'gcloud container clusters get-credentials {} --region us-west1-a'
        .format(cluster_name))
    return json.loads(
        handle_process('kubectl get pod nginx-test-pod --output="json"'))


def node_instance_by_name(name):
    for node_instance in node_instances():
        if node_instance['node_id'] == name:
            return node_instance
    raise Exception('No node instances found.')


def nodes():
    return cloudify_exec('cfy nodes list')


def node_instances():
    return cloudify_exec('cfy node-instances list')


def node_instance(node_instance_id):
    return cloudify_exec('cfy node-instances get {}'.format(node_instance_id))


def runtime_properties(node_instance_id):
    return node_instance(node_instance_id)['runtime_properties']
