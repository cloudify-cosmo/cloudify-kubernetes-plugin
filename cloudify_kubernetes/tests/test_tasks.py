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

from mock import MagicMock, Mock, patch, mock_open
import unittest
from datetime import datetime

from cloudify.exceptions import (RecoverableError,
                                 OperationRetry,
                                 NonRecoverableError)
from cloudify.mocks import MockCloudifyContext
from cloudify.manager import DirtyTrackingDict
from cloudify.state import current_ctx

from cloudify_kubernetes.decorators import RELATIONSHIP_TYPE_MANAGED_BY_MASTER
from cloudify_kubernetes.k8s.mapping import (
    KubernetesApiMapping,
    KubernetesSingleOperationApiMapping
)
import cloudify_kubernetes.tasks as tasks

FILE_YAML = """
apiVersion: v1
kind: Pod
metadata:
  name: pod-c
spec:
  containers:
  - name: pod-c-1
    image: "centos:7"
    command: ["/bin/bash"]
    stdin: true
    tty: true
    securityContext:
      privileged: true
---
apiVersion: v1
kind: Pod
metadata:
  name: pod-d
spec:
  containers:
  - name: pod-d-1
    image: "centos:7"
    command: ["/bin/bash"]
    stdin: true
    tty: true
    securityContext:
      privileged: true
"""


class TestTasks(unittest.TestCase):

    def setUp(self):
        super(TestTasks, self).setUp()

        self.patch_mock_mappings = patch(
            'cloudify_kubernetes.k8s.mapping.SUPPORTED_API_MAPPINGS',
            {
                'Pod': KubernetesApiMapping(
                    create=KubernetesSingleOperationApiMapping(
                        api='api_client_version',
                        method='create',
                        payload='api_payload_version'
                    ),
                    read=KubernetesSingleOperationApiMapping(
                        api='api_client_version',
                        method='read',
                    ),
                    update=KubernetesSingleOperationApiMapping(
                        api='api_client_version',
                        method='update',
                    ),
                    delete=KubernetesSingleOperationApiMapping(
                        api='api_client_version',
                        method='delete',
                        payload='api_payload_version'
                    ),
                )
            }
        )

        self.patch_mock_mappings.start()

        self.mock_loader = MagicMock(return_value=MagicMock())
        self.mock_client = MagicMock()

        self.client_api = MagicMock()

        def del_func(body, name, first):
            class _DelResult(object):
                def __init__(self, body, name, first):
                    self.body = body,
                    self.name = name,
                    self.first = first

                def to_dict(self):
                    return self.body, self.name, self.first

            return _DelResult(body, name, first)

        def create_func(body, first):
            mock = MagicMock()
            mock.to_dict = MagicMock(return_value={
                'body': body, 'first': first
            })
            return mock

        def update_func(body, first):
            mock = MagicMock()
            mock.to_dict = MagicMock(return_value={
                'body': body, 'first': first
            })
            return mock

        self.client_api.delete = del_func
        self.client_api.create = create_func
        self.client_api.update = update_func

        self.mock_client.api_client_version = MagicMock(
            return_value=self.client_api
        )

        self.mock_client.api_payload_version = MagicMock(
            return_value={'payload_param': 'payload_value'}
        )

        self.patch_mock_loader = patch(
            'kubernetes.config.load_kube_config', self.mock_loader
        )
        self.patch_mock_loader.start()

        self.patch_mock_client = patch(
            'kubernetes.client', self.mock_client
        )
        self.patch_mock_client.start()

    def tearDown(self):
        current_ctx.clear()
        self.patch_mock_client.stop()
        self.patch_mock_loader.stop()
        self.patch_mock_mappings.stop()
        super(TestTasks, self).tearDown()

    def _prepare_master_node(self, api_mapping=None, external=False,
                             create=False):
        node = MagicMock()
        node.properties = {
            'configuration': {
                'blueprint_file_name': 'kubernetes.conf'
            }
        }

        managed_master_node = MagicMock()
        managed_master_node.type = RELATIONSHIP_TYPE_MANAGED_BY_MASTER
        managed_master_node.target.node = node

        properties = {
            'use_external_resource': external,
            'validate_resource_status': True,
            'definition': {
                'apiVersion': 'v1',
                'metadata': 'c',
                'spec': 'd'
            },
            'options': {
                'first': 'second'
            }
        }

        if api_mapping:
            properties['api_mapping'] = api_mapping

        _ctx = MockCloudifyContext(
            node_id="test_id",
            node_name="test_name",
            deployment_id="test_name",
            properties=properties,
            runtime_properties=DirtyTrackingDict(
                {} if create else {
                    'kubernetes': {
                        'metadata': {
                            'name': "kubernetes_id"
                        }
                    }
                }
            ),
            relationships=[managed_master_node],
            operation={'retry_number': 0}
        )

        _ctx.node.type_hierarchy = \
            ['cloudify.nodes.Root',
             'cloudify.kubernetes.resources.ResourceBase',
             'cloudify.kubernetes.resources.BlueprintDefinedResource',
             'cloudify.kubernetes.resources.Pod']

        current_ctx.set(_ctx)
        return managed_master_node, _ctx

    def test_cleanuped_resource(self):
        ob = Mock()
        ob.to_dict = MagicMock(return_value={
            'a': 'b',
            'c': [{
                'd': 'f',
                'f': 'e',
                'date': datetime(2017, 1, 1, 1, 1),
                'g': None
            }, None]
        })
        self.assertEqual(tasks.JsonCleanuper(ob).to_dict(), {
            'a': 'b',
            'c': [{
                'd': 'f',
                'f': 'e',
                'date': '2017-01-01 01:01:00',
                'g': None
            }, None]
        })

        ob.to_dict = MagicMock(return_value=[
            'a', 'b', [datetime(2017, 1, 2, 1, 1)]
        ])
        self.assertEqual(tasks.JsonCleanuper(ob).to_dict(), [
            'a', 'b', ['2017-01-02 01:01:00']
        ])

    def test_retrieve_id(self):
        _, _ctx = self._prepare_master_node()
        self.assertEqual(tasks._retrieve_id(_ctx.instance),
                         'kubernetes_id')

    def test_retrieve_id_with_file(self):
        _, _ctx = self._prepare_master_node()
        _ctx.instance.runtime_properties[
            tasks.INSTANCE_RUNTIME_PROPERTY_KUBERNETES
        ] = {"other_field": {
            'metadata': {
                'name': "id"
            }
        }}
        self.assertEqual(tasks._retrieve_id(_ctx.instance, "other_field"),
                         'id')

    def test_do_resource_status_check_unknown(self):
        # never raise exception on unknown types
        _, __ = self._prepare_master_node()
        tasks._do_resource_status_check("unknown", {})

    def test_do_resource_status_check_pod(self):
        # never raise exception on 'Running', 'Succeeded'
        self._prepare_master_node()
        tasks._do_resource_status_check("Pod", {
            'status': {'phase': 'Running'}
        })
        tasks._do_resource_status_check("Pod", {
            'status': {'phase': 'Succeeded'}
        })
        tasks._do_resource_status_check("Pod", {
            'status': {'phase': 'Other'}
        })

    def test_do_resource_status_check_pod_retry(self):
        # raise exception on 'Pending', 'Unknown'
        self._prepare_master_node()

        with self.assertRaises(OperationRetry) as error:
            tasks._do_resource_status_check("Pod", {
                'status': {'phase': 'Pending'}
            })
        self.assertEqual(
            str(error.exception),
            "Status is {'phase': 'Pending'}"
        )

        with self.assertRaises(OperationRetry) as error:
            tasks._do_resource_status_check("Pod", {
                'status': {'phase': 'Unknown'}
            })
        self.assertEqual(
            str(error.exception),
            "Status is {'phase': 'Unknown'}"
        )

    def test_do_resource_status_check_pod_failed(self):
        # raise exception on 'Failed'
        self._prepare_master_node()

        with self.assertRaises(NonRecoverableError) as error:
            tasks._do_resource_status_check("Pod", {
                'status': {'phase': 'Failed'}
            })
        self.assertEqual(
            str(error.exception),
            "Status is {'phase': 'Failed'}"
        )

    def test_do_resource_status_check_service_fail(self):
        # raise exception on empty balancer
        _, _ctx = self._prepare_master_node()
        current_ctx.set(_ctx)
        with self.assertRaises(OperationRetry) as error:
            tasks._do_resource_status_check("Service", {
                'spec': {'type': 'Ingress'},
                'status': {'load_balancer': {'ingress': None}}
            })
        self.assertEqual(
            str(error.exception),
            "Status is {'load_balancer': {'ingress': None}}"
        )

    def test_do_resource_status_check_deployment(self):
        self._prepare_master_node()
        tasks._do_resource_status_check("Deployment", {
            'status': {'conditions': [{'type': 'Available'}],
                       'unavailable_replicas': None}
        })

    def test_do_resource_status_check_persistent_volume_claim(self):
        self._prepare_master_node()
        tasks._do_resource_status_check("PersistentVolumeClaim", {
            'status': {'phase': 'Bound'}
        })

        tasks._do_resource_status_check("PersistentVolumeClaim", {
            'status': {'phase': 'Pending'}
        })

        tasks._do_resource_status_check("PersistentVolumeClaim", {
            'status': {'phase': 'Available'}
        })

    def test_do_resource_status_check_persistent_volume_claim_retry(self):
        self._prepare_master_node()
        with self.assertRaises(OperationRetry) as error:
            tasks._do_resource_status_check("PersistentVolumeClaim", {
                'status': {'phase': 'Unknown'}
            })

        self.assertEqual(
            str(error.exception),
            "Status is {'phase': 'Unknown'}"
        )

        with self.assertRaises(OperationRetry) as error:
            tasks._do_resource_status_check("PersistentVolumeClaim", {
                'status': {'phase': None}
            })

        self.assertEqual(
            str(error.exception),
            "Status is {'phase': None}"
        )

    def test_do_resource_status_check_persistent_volume(self):
        self._prepare_master_node()
        tasks._do_resource_status_check("PersistentVolume", {
            'status': 'Bound'
        })

        tasks._do_resource_status_check("PersistentVolume", {
            'status': 'Available'
        })

    def test_do_resource_status_check_persistent_volume_retry(self):
        self._prepare_master_node()

        with self.assertRaises(OperationRetry) as error:
            tasks._do_resource_status_check("PersistentVolume", {
                'status': {'phase': 'Unknown'}
            })
        self.assertEqual(
            str(error.exception),
            "Status is {'phase': 'Unknown'}"
        )

    def test_do_resource_status_check_replica_set(self):
        self._prepare_master_node()
        tasks._do_resource_status_check("ReplicaSet", {
            'status': {'ready_replicas': 2, 'replicas': 2}
        })

    def test_do_resource_status_check_replica_set_retry(self):
        self._prepare_master_node()

        with self.assertRaises(OperationRetry) as error:
            tasks._do_resource_status_check("ReplicaSet", {
                'status': {'ready_replicas': None, 'replicas': 0}
            })
        self.assertEqual(
            str(error.exception),
            "Status is {'ready_replicas': None, 'replicas': 0}"
        )

    def test_do_resource_status_check_replication_controller(self):
        self._prepare_master_node()
        tasks._do_resource_status_check("ReplicationController", {
            'status': {'ready_replicas': 2, 'replicas': 2}
        })

    def test_do_resource_status_check_replication_controller_retry(self):
        self._prepare_master_node()

        with self.assertRaises(OperationRetry) as error:
            tasks._do_resource_status_check("ReplicationController", {
                'status': {'ready_replicas': None, 'replicas': 0}
            })
        self.assertEqual(
            str(error.exception),
            "Status is {'ready_replicas': None, 'replicas': 0}"
        )

    def test_do_resource_create(self):
        self._prepare_master_node()

        expected_value = {
            'kubernetes': {
                'body': {'payload_param': 'payload_value'},
                'first': 'second'
            }
        }

        class _Result(object):
            def to_dict(self):
                return expected_value

        class _CreateResource(object):
            def __call__(self, api_mapping, resource_definition, options):
                if api_mapping == 'fake_api_mapping':
                    if resource_definition == 'fake_resource_definition':
                        if options['first'] == 'second':
                            return _Result()

        client = MagicMock()
        client.create_resource = _CreateResource()

        result = tasks._do_resource_create(
            client=client,
            api_mapping='fake_api_mapping',
            resource_definition='fake_resource_definition'
        )

        self.assertEqual(result, expected_value)

    def test_external_do_resource_create(self):
        self._prepare_master_node(external=True)

        expected_value = {
            'kubernetes': {
                'body': {'payload_param': 'payload_value'},
                'first': 'second'
            }
        }
        fake_resource_def = MagicMock()
        setattr(
            fake_resource_def, 'metadata', {'name': 'name'})

        class _Result(object):
            def to_dict(self):
                return expected_value

        class _ReadResource(object):
            def __call__(self, api_mapping, resource_definition, options):
                if api_mapping == 'fake_api_mapping':
                    if resource_definition == \
                            fake_resource_def.metadata['name']:
                        if options['first'] == 'second':
                            return _Result()

        client = MagicMock()
        client.read_resource = _ReadResource()

        result = tasks._do_resource_create(
            client=client,
            api_mapping='fake_api_mapping',
            resource_definition=fake_resource_def
        )

        self.assertEqual(result, expected_value)

    def test_do_resource_update(self):
        self._prepare_master_node()

        expected_value = {
            'kubernetes': {
                'body': {'payload_param': 'payload_value'},
                'first': 'second'
            }
        }

        class _Result(object):
            def to_dict(self):
                return expected_value

        class _UpdateResource(object):
            def __call__(self, api_mapping, resource_definition, options):
                if api_mapping == 'fake_api_mapping':
                    if resource_definition == 'fake_resource_definition':
                        if options['first'] == 'second':
                            return _Result()

        client = MagicMock()
        client.update_resource = _UpdateResource()

        result = tasks._do_resource_update(
            client=client,
            api_mapping='fake_api_mapping',
            resource_definition='fake_resource_definition'
        )

        self.assertEqual(result, expected_value)

    def test_do_resource_delete(self):
        self._prepare_master_node()

        expected_value = {
            'kubernetes': {
                'body': {'payload_param': 'payload_value'},
                'first': 'second'
            }
        }

        class _Result(object):
            def to_dict(self):
                return expected_value

        class _DeleteResource(object):
            def __call__(self, api_mapping, resource_definition, id, options):
                if api_mapping == 'fake_api_mapping':
                    if resource_definition == 'fake_resource_definition':
                        if id == 'fake_id':
                            if options['first'] == 'second':
                                return _Result()

        client = MagicMock()
        client.delete_resource = _DeleteResource()

        result = tasks._do_resource_delete(
            client=client,
            api_mapping='fake_api_mapping',
            resource_definition='fake_resource_definition',
            resource_id='fake_id'
        )

        self.assertEqual(result, expected_value)

    def test_external_do_resource_delete(self):
        self._prepare_master_node(external=True)

        expected_value = {
            'kubernetes': {
                'body': {'payload_param': 'payload_value'},
                'first': 'second'
            }
        }
        fake_resource_def = MagicMock()
        setattr(
            fake_resource_def, 'metadata', {'name': 'name'})

        class _Result(object):
            def to_dict(self):
                return expected_value

        class _ReadResource(object):
            def __call__(self, api_mapping, resource_definition, options):
                if api_mapping == 'fake_api_mapping':
                    if resource_definition == 'fake_id':
                        if options['first'] == 'second':
                            return _Result()

        client = MagicMock()
        client.read_resource = _ReadResource()

        result = tasks._do_resource_delete(
            client=client,
            api_mapping='fake_api_mapping',
            resource_definition=fake_resource_def,
            resource_id='fake_id'
        )

        self.assertEqual(result, expected_value)

    def test_resource_create_RecoverableError(self):
        _, _ctx = self._prepare_master_node()

        with self.assertRaises(RecoverableError) as error:
            tasks.resource_create(
                client=MagicMock(),
                api_mapping=MagicMock(),
                resource_definition=MagicMock()
            )

        self.assertEqual(
            str(error.exception),
            "Cannot initialize Kubernetes API - no suitable configuration "
            "variant found for {'blueprint_file_name': 'kubernetes.conf'} "
            "properties"
        )

    def test_resource_create(self):
        _, _ctx = self._prepare_master_node(create=True)

        mock_isfile = MagicMock(return_value=True)

        _ctx.download_resource = MagicMock(return_value="downloaded_resource")

        with patch('os.path.isfile', mock_isfile):
            with patch(
                    'cloudify_kubernetes.k8s.config.'
                    'kubernetes.config.load_kube_config',
                    MagicMock()
            ):
                tasks.resource_create(
                    client=MagicMock(),
                    api_mapping=MagicMock(),
                    resource_definition=MagicMock()
                )

        self.assertEqual(_ctx.instance.runtime_properties, {
            'kubernetes': {
                'body': {'payload_param': 'payload_value'},
                'first': 'second'
            }
        })

    def test_resource_delete_RecoverableError(self):
        _, _ctx = self._prepare_master_node()

        with self.assertRaises(RecoverableError) as error:
            tasks.resource_delete(
                client=MagicMock(),
                api_mapping=MagicMock(),
                resource_definition=MagicMock()
            )

        self.assertEqual(
            str(error.exception),
            "Cannot initialize Kubernetes API - no suitable configuration "
            "variant found for {'blueprint_file_name': 'kubernetes.conf'} "
            "properties"
        )

    def test_resource_delete(self):
        _, _ctx = self._prepare_master_node()

        mock_isfile = MagicMock(return_value=True)

        _ctx.download_resource = MagicMock(return_value="downloaded_resource")

        with patch('os.path.isfile', mock_isfile):
            with patch(
                    'cloudify_kubernetes.k8s.config.'
                    'kubernetes.config.load_kube_config',
                    MagicMock()
            ):
                with patch(
                        'cloudify_kubernetes.tasks._do_resource_read',
                        MagicMock()):
                    with self.assertRaises(OperationRetry):
                        tasks.resource_delete(
                            client=MagicMock(),
                            api_mapping=MagicMock(),
                            resource_definition=MagicMock()
                        )

    def test_custom_resource_create(self):
        # TODO
        pass

    def test_custom_resource_delete(self):
        # TODO
        pass

    def test_file_resource_create(self):
        _, _ctx = self._prepare_master_node()

        _ctx.node.properties['file'] = {"resource_path": 'abc.yaml'}
        _ctx.download_resource_and_render = MagicMock(return_value="new_path")

        expected_value = {
            'metadata': {'name': 'check_id'}
        }

        class _Result(object):
            def to_dict(self):
                return expected_value

        client = MagicMock()
        client.create_resource = Mock(return_value=_Result())

        mock_isfile = MagicMock(return_value=True)
        with patch('os.path.isfile', mock_isfile):
            with patch(
                    'cloudify_kubernetes.decorators.'
                    'CloudifyKubernetesClient',
                    MagicMock(return_value=client)
            ):
                with patch(
                        'cloudify_kubernetes.utils.open',
                        mock_open(read_data=FILE_YAML)
                ) as file_mock:
                    tasks.file_resource_create(
                        client=client,
                        api_mapping=None,
                        resource_definition=None
                    )
                file_mock.assert_called_with('new_path')
        self.assertEqual(_ctx.instance.runtime_properties, {
            'kubernetes': {
                'abc.yaml#0': {
                    'metadata': {'name': 'check_id'}
                },
                'abc.yaml#1': {
                    'metadata': {
                        'name': 'check_id'
                    }
                },
                'metadata': {'name': 'kubernetes_id'}
            }
        })
        self.assertEqual(client.create_resource.call_count, 2)

    def test_file_resource_delete(self):
        _, _ctx = self._prepare_master_node()
        _ctx.instance.runtime_properties['kubernetes'] = {
            'abc.yaml#0': {
                'metadata': {'name': 'check_id'}
            },
            'abc.yaml#1': {
                'metadata': {
                    'name': 'check_id'
                }
            },
            'metadata': {'name': 'kubernetes_id'}
        }

        _ctx.node.properties['file'] = {"resource_path": 'abc.yaml'}
        _ctx.download_resource_and_render = MagicMock(return_value="new_path")

        expected_value = {
            'kubernetes': {
                'body': {'payload_param': 'payload_value'},
                'first': 'second'
            }
        }

        class _Result(object):
            def to_dict(self):
                return expected_value

        client = MagicMock()
        client.delete_resource = Mock(return_value=_Result())

        mock_isfile = MagicMock(return_value=True)
        with patch('os.path.isfile', mock_isfile):
            with patch(
                    'cloudify_kubernetes.decorators.'
                    'CloudifyKubernetesClient',
                    MagicMock(return_value=client)
            ):
                with patch(
                        'cloudify_kubernetes.utils.open',
                        mock_open(read_data=FILE_YAML)
                ) as file_mock:
                    tasks.file_resource_delete(
                        client=client,
                        api_mapping=None,
                        resource_definition=None
                    )
                file_mock.assert_called_with('new_path')
        self.assertEqual(client.delete_resource.call_count, 2)

    def test_multiple_file_resource_create(self):
        _, _ctx = self._prepare_master_node(create=True)

        _ctx.node.properties['files'] = [{"resource_path": 'abc.yaml'}]
        _ctx.download_resource_and_render = MagicMock(return_value="new_path")

        expected_value = {
            'metadata': {'name': 'check_id'}
        }

        class _Result(object):
            def to_dict(self):
                return expected_value

        client = MagicMock()
        client.create_resource = Mock(return_value=_Result())

        mock_isfile = MagicMock(return_value=True)
        with patch('os.path.isfile', mock_isfile):
            with patch(
                    'cloudify_kubernetes.decorators.'
                    'CloudifyKubernetesClient',
                    MagicMock(return_value=client)
            ):
                with patch(
                        'cloudify_kubernetes.utils.open',
                        mock_open(read_data=FILE_YAML)
                ) as file_mock:
                    tasks.multiple_file_resource_create(
                        client=client,
                        api_mapping=None,
                        resource_definition=None
                    )
                file_mock.assert_called_with('new_path')
        self.assertEqual(_ctx.instance.runtime_properties, {
            'kubernetes': {
                'abc.yaml#0': {'metadata': {'name': 'check_id'}},
                'abc.yaml#1': {'metadata': {'name': 'check_id'}}
            }
        })
        self.assertEqual(client.create_resource.call_count, 2)

    def test_multiple_file_resource_delete(self):
        _, _ctx = self._prepare_master_node()
        _ctx.instance.runtime_properties['kubernetes'] = {
            'abc.yaml#0': {
                'metadata': {
                    'name': 'check_id'
                }
            },
            'abc.yaml#1': {
                'metadata': {
                    'name': 'check_id'
                }
            }
        }

        _ctx.node.properties['files'] = [{"resource_path": 'abc.yaml'}]
        _ctx.download_resource_and_render = MagicMock(return_value="new_path")

        expected_value = {
            'kubernetes': {
                'body': {'payload_param': 'payload_value'},
                'first': 'second'
            }
        }

        class _Result(object):
            def to_dict(self):
                return expected_value

        client = MagicMock()
        client.delete_resource = Mock(return_value=_Result())

        mock_isfile = MagicMock(return_value=True)
        with patch('os.path.isfile', mock_isfile):
            with patch(
                    'cloudify_kubernetes.decorators.'
                    'CloudifyKubernetesClient',
                    MagicMock(return_value=client)
            ):
                with patch(
                        'cloudify_kubernetes.utils.open',
                        mock_open(read_data=FILE_YAML)
                ) as file_mock:
                    tasks.multiple_file_resource_delete(
                        client=client,
                        api_mapping=None,
                        resource_definition=None
                    )
                file_mock.assert_called_with('new_path')
        self.assertEqual(client.delete_resource.call_count, 2)


if __name__ == '__main__':
    unittest.main()
