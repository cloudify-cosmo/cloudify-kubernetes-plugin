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

from ecosystem_tests.dorkl.commands import handle_process
from ecosystem_tests.ecosystem_tests_cli.logger import logger
from ecosystem_tests.nerdl.api import (
    create_secret,
    with_client,
    get_node_instance,
    list_node_instances,
    upload_blueprint,
    create_deployment,
    wait_for_install,
    cleanup_on_failure)


TEST_ID = environ.get('__ECOSYSTEM_TEST_ID', 'plugin-examples')


@pytest.mark.dependency()
def test_update(*_, **__):
    deployment_id = TEST_ID + '-update'
    setup_cli()
    try:
        # Upload Cloud Watch Blueprint
        upload_blueprint(
            'examples/file-test.yaml',
            deployment_id)
        # Create Cloud Watch Deployment with Instance ID input
        create_deployment(
            deployment_id,
            deployment_id,
            {
                "resource_path": "resources/pod.yaml"
            }
        )
        # Install Cloud Watch Deployment
        wait_for_install(deployment_id, 300)
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
        wait_for_workflow(
            deployment_id,
            'update_resource_definition',
            300,
            params=tmp
        )
        os.remove(tmp.name)
        after_update = get_pod_info()
        assert after_install['spec']['containers'][0]['image'] == 'nginx:stable'
        assert after_update['spec']['containers'][0]['image'] == 'nginx:latest'
        # Uninstall Cloud Watch Deployment
        wait_for_uninstall(deployment_id, 300)
    except:
        cleanup_on_failure(deployment_id)


def setup_cli():
    cluster_name = runtime_properties(
        node_instance_by_name('kubernetes-cluster')['id'])['name']
    capabilities = get_capabilities('gcp-gke')
    logger.info('capabilities: {}'.format(capabilities))
    create_secret('kubernetes_endpoint', capabilities['endpoint']['value'])
    with open('gcp.json', 'wb') as outfile:
        creds = base64.b64decode(os.environ['gcp_credentials'])
        outfile.write(creds)
    handle_process('gcloud auth activate-service-account --key-file gcp.json')
    handle_process(
        'gcloud container clusters get-credentials {} --region us-west1-a'
        .format(cluster_name))


@with_client
def get_capabilities(dep_id, client):
    dep = client.deployments.capabilities.get(dep_id)
    return dep.capabilities


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


def node_instances():
    return list_node_instances(TEST_ID)


def runtime_properties(node_instance_id):
    return get_node_instance(node_instance_id)['runtime_properties']
