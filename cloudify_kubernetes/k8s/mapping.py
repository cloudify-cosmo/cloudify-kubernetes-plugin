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

from .exceptions import KuberentesMappingNotFoundError


class KubernetesSingleOperationApiMapping(object):

    def __init__(self, api, method, payload=None):
        self.api = api
        self.method = method
        self.payload = payload


class KubernetesApiMapping(object):

    def __init__(self, create, read, update, delete,
                 start_status=None, stop_status=None):

        if isinstance(create, dict):
            create = KubernetesSingleOperationApiMapping(**create)

        if isinstance(read, dict):
            read = KubernetesSingleOperationApiMapping(**read)

        if isinstance(update, dict):
            update = KubernetesSingleOperationApiMapping(**update)

        if isinstance(delete, dict):
            delete = KubernetesSingleOperationApiMapping(**delete)

        self.create = create
        self.read = read
        self.update = update
        self.delete = delete
        self._start_status = start_status or []
        self._stop_status = stop_status or []

    @property
    def start_status(self):
        return self._start_status

    @property
    def stop_status(self):
        return self._stop_status


SUPPORTED_API_MAPPINGS = {
    'StatefulSet': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='create_namespaced_stateful_set',
            payload='V1StatefulSet'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='read_namespaced_stateful_set',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='patch_namespaced_stateful_set',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='delete_namespaced_stateful_set',
            payload='V1DeleteOptions'
        ),
    ),
    'DaemonSet': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='create_namespaced_daemon_set',
            payload='V1DaemonSet'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='read_namespaced_daemon_set',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='patch_namespaced_daemon_set',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='delete_namespaced_daemon_set',
            payload='V1DeleteOptions'
        ),
    ),
    'PodSecurityPolicy': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='PolicyV1beta1Api',
            method='create_pod_security_policy',
            payload='V1NetworkPolicy'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='PolicyV1beta1Api',
            method='read_pod_security_policy',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='PolicyV1beta1Api',
            method='patch_pod_security_policy',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='PolicyV1beta1Api',
            method='delete_pod_security_policy',
            payload='V1DeleteOptions'
        ),
    ),
    'NetworkPolicy': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='NetworkingV1Api',
            method='create_namespaced_network_policy',
            payload='V1NetworkPolicy'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='NetworkingV1Api',
            method='read_namespaced_network_policy',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='NetworkingV1Api',
            method='patch_namespaced_network_policy',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='NetworkingV1Api',
            method='delete_namespaced_network_policy',
            payload='V1DeleteOptions'
        ),
    ),
    'Node': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='create_node',
            payload='V1Node'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='read_node',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='patch_node',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_node',
            payload='V1DeleteOptions'
        ),
    ),
    'ClusterRoleBinding': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1beta1Api',
            method='create_cluster_role_binding',
            payload='V1beta1ClusterRoleBinding'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1beta1Api',
            method='read_cluster_role_binding',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1beta1Api',
            method='patch_cluster_role_binding',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1beta1Api',
            method='delete_cluster_role_binding',
            payload='V1DeleteOptions'
        ),
    ),
    'ClusterRole': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='create_cluster_role',
            payload='V1beta1ClusterRole'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='read_cluster_role',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='patch_cluster_role'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='delete_cluster_role',
            payload='V1DeleteOptions'
        ),
    ),
    'Deployment': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='create_namespaced_deployment',
            payload='V1Deployment'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='read_namespaced_deployment',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='patch_namespaced_deployment',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='delete_namespaced_deployment',
            payload='V1DeleteOptions'
        ),
    ),
    'Pod': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='create_namespaced_pod',
            payload='V1Pod'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='read_namespaced_pod',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='patch_namespaced_pod'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_namespaced_pod',
            payload='V1DeleteOptions'
        ),
    ),
    'ReplicaSet': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='create_namespaced_replica_set',
            payload='V1ReplicaSet'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='read_namespaced_replica_set',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='patch_namespaced_replica_set'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='delete_namespaced_replica_set',
            payload='V1DeleteOptions'
        ),
    ),
    'ReplicationController': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='create_namespaced_replication_controller',
            payload='V1ReplicationController'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='read_namespaced_replication_controller',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='patch_namespaced_replication_controller',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_collection_namespaced_replication_controller',
        ),
    ),
    'Service': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='create_namespaced_service',
            payload='V1Service'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='read_namespaced_service',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='patch_namespaced_service'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_namespaced_service',
            payload='V1DeleteOptions'
        ),
    ),
    'Ingress': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='NetworkingV1beta1Api',
            method='create_namespaced_ingress',
            payload='NetworkingV1beta1Ingress'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='NetworkingV1beta1Api',
            method='read_namespaced_ingress',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='NetworkingV1beta1Api',
            method='patch_namespaced_ingress'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='NetworkingV1beta1Api',
            method='delete_namespaced_ingress',
            payload='V1DeleteOptions'
        ),
    ),
    'PersistentVolumeClaim': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='create_namespaced_persistent_volume_claim',
            payload='V1PersistentVolumeClaim'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='read_namespaced_persistent_volume_claim',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='patch_namespaced_persistent_volume_claim'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_namespaced_persistent_volume_claim',
            payload='V1DeleteOptions'
        ),
    ),
    'PersistentVolume': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='create_persistent_volume',
            payload='V1PersistentVolume'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='read_persistent_volume',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='patch_persistent_volume'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_persistent_volume',
            payload='V1DeleteOptions'
        ),
    ),
    'StorageClass': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='StorageV1beta1Api',
            method='create_storage_class',
            payload='V1beta1StorageClass'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='StorageV1beta1Api',
            method='read_storage_class',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='StorageV1beta1Api',
            method='patch_storage_class'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='StorageV1beta1Api',
            method='delete_storage_class',
            payload='V1DeleteOptions'
        ),
    ),
    'ConfigMap': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='create_namespaced_config_map',
            payload='V1ConfigMap'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='read_namespaced_config_map',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='patch_namespaced_config_map'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_namespaced_config_map',
            payload='V1DeleteOptions'
        ),
    ),
    'Secret': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='create_namespaced_secret',
            payload='V1Secret'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='read_namespaced_secret',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='patch_namespaced_secret'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_namespaced_secret',
            payload='V1DeleteOptions'
        ),
    ),
    'ServiceAccount': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='create_namespaced_service_account',
            payload='V1ServiceAccount'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='read_namespaced_service_account',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='patch_namespaced_service_account'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_namespaced_service_account',
            payload='V1DeleteOptions'
        ),
    ),
    'Role': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='create_namespaced_role',
            payload='V1Role'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='read_namespaced_role',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='patch_namespaced_role'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='delete_namespaced_role',
            payload='V1DeleteOptions'
        ),
    ),
    'RoleBinding': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='create_namespaced_role_binding',
            payload='V1RoleBinding'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='read_namespaced_role_binding',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='patch_namespaced_role_binding'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='delete_namespaced_role_binding',
            payload='V1DeleteOptions'
        ),
    ),
    'CustomResourceDefinition': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='ApiextensionsV1beta1Api',
            method='create_custom_resource_definition',
            payload='V1beta1CustomResourceDefinition'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='ApiextensionsV1beta1Api',
            method='read_custom_resource_definition',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='ApiextensionsV1beta1Api',
            method='patch_custom_resource_definition'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='ApiextensionsV1beta1Api',
            method='delete_custom_resource_definition',
            payload='V1DeleteOptions'
        ),
    ),

}


def get_mapping(kind):
    if kind in SUPPORTED_API_MAPPINGS:
        return SUPPORTED_API_MAPPINGS[kind]

    raise KuberentesMappingNotFoundError(
        'Cloud not find API mapping for {0} kind of kubernetes resource'
        .format(kind)
    )
