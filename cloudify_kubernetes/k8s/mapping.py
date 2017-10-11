########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from .exceptions import KuberentesMappingNotFoundError


class KubernetesSingleOperationApiMapping(object):

    def __init__(self, api, method, payload=None):
        self.api = api
        self.method = method
        self.payload = payload


class KubernetesApiMapping(object):

    def __init__(self, create, read, delete):
        if isinstance(create, dict):
            create = KubernetesSingleOperationApiMapping(**create)

        if isinstance(read, dict):
            read = KubernetesSingleOperationApiMapping(**read)

        if isinstance(delete, dict):
            delete = KubernetesSingleOperationApiMapping(**delete)

        self.create = create
        self.read = read
        self.delete = delete


SUPPORTED_API_MAPPINGS = {
    'Deployment': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='ExtensionsV1beta1Api',
            method='create_namespaced_deployment',
            payload='V1beta1Deployment'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='ExtensionsV1beta1Api',
            method='read_namespaced_deployment',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='ExtensionsV1beta1Api',
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
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_namespaced_pod',
            payload='V1DeleteOptions'
        ),
    ),
    'ReplicaSet': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='ExtensionsV1beta1Api',
            method='create_namespaced_replica_set',
            payload='V1beta1ReplicaSet'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='ExtensionsV1beta1Api',
            method='read_namespaced_replica_set',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='ExtensionsV1beta1Api',
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
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_namespaced_service',
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
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_namespaced_config_map',
            payload='V1DeleteOptions'
        ),
    )
}


def get_mapping(kind):
    if kind in SUPPORTED_API_MAPPINGS:
        return SUPPORTED_API_MAPPINGS[kind]

    raise KuberentesMappingNotFoundError(
        'Cloud not find API mapping for {0} kind of kubernetes resource'
        .format(kind)
    )
