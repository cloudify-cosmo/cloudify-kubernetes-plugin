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

import inspect
from re import search

from kubernetes import client as kube_api

from .exceptions import KuberentesMappingNotFoundError


class KubernetesSingleOperationApiMapping(object):

    def __init__(self, api, method, payload=None):
        self.api = api
        self.method = method
        self.payload = payload
        self.kubernetes_apis = self.get_kubernetes_apis()

    @staticmethod
    def get_kubernetes_apis():
        """ Create a list of all available APIs in the current version of
        Kubernetes Python library.

        :return:
        """
        kubernetes_apis = {}
        for name, obj in inspect.getmembers(kube_api):
            try:
                path = inspect.getfile(obj)
            except TypeError:
                path = None
            if path and 'kubernetes/client/api' in path:
                kubernetes_apis[name] = obj
        return kubernetes_apis

    def get_apis_with_method(self):
        """ Get a list of APIs that support self.method function.

        :return:
        """
        alternates = []
        for name, value in self.kubernetes_apis.items():
            if name == self.api:
                continue
            method_obj = getattr(value, self.method, None)
            if not method_obj:
                continue
            if self.payload:
                payload_name = self.get_method_payload_name(method_obj)
                alternates.append(
                    KubernetesSingleOperationApiMapping(
                        api=name,
                        method=self.method,
                        payload=payload_name
                    )
                )
            else:
                alternates.append(
                    KubernetesSingleOperationApiMapping(
                        api=name,
                        method=self.method
                    )
                )
        return alternates

    @staticmethod
    def get_method_payload_name(method_obj):
        """All Kubernetes API methods have a doc string that matches the
        pattern "param ObjectName body", which is our "payload" object.

        :param str method_obj: The name of the API method, for example
            create_namespaced_ingress.
        :return:
        """
        body_param_pattern = "param\\s(.*?)\\sbody"
        docs = inspect.getdoc(method_obj)
        body_param_result = search(body_param_pattern, docs)
        return_param_pattern = "\\:return\\:\\s(.*?)\\n"
        return_param_result = search(return_param_pattern, docs)
        if not body_param_result and not return_param_pattern:
            return
        elif body_param_result and body_param_result.group(1) != 'object':
            return body_param_result.group(1)
        elif 'tuple' not in return_param_result.group(1):
            return return_param_result.group(1)

    @property
    def alternates(self):
        return self.get_apis_with_method()


class KubernetesApiMapping(object):

    def __init__(self, create, read, update, delete):

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
            method='replace_namespaced_stateful_set',
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
            method='replace_namespaced_daemon_set',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='AppsV1Api',
            method='delete_namespaced_daemon_set',
            payload='V1DeleteOptions'
        ),
    ),
    'PodSecurityPolicy': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='PolicyV1Api',
            method='create_pod_security_policy',
            payload='V1NetworkPolicy'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='PolicyV1Api',
            method='read_pod_security_policy',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='PolicyV1Api',
            method='patch_pod_security_policy',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='PolicyV1Api',
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
            method='replace_namespaced_network_policy',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='NetworkingV1Api',
            method='delete_namespaced_network_policy',
            payload='V1DeleteOptions'
        ),
    ),
    'Namespace': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='create_namespace',
            payload='V1Namespace'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='read_namespace',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='patch_namespace',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_namespace',
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
            api='RbacAuthorizationV1Api',
            method='create_cluster_role_binding',
            payload='V1ClusterRoleBinding'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='read_cluster_role_binding',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='patch_cluster_role_binding',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='delete_cluster_role_binding',
            payload='V1DeleteOptions'
        ),
    ),
    'ClusterRole': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='create_cluster_role',
            payload='V1ClusterRole'
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
            method='replace_namespaced_deployment',
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
            method='replace_namespaced_pod'
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
            method='replace_namespaced_replica_set'
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
            method='replace_namespaced_replication_controller',
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
            method='replace_namespaced_service'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CoreV1Api',
            method='delete_namespaced_service',
            payload='V1DeleteOptions'
        ),
    ),
    'Ingress': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='NetworkingV1Api',
            method='create_namespaced_ingress',
            payload='V1Ingress'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='NetworkingV1Api',
            method='read_namespaced_ingress',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='NetworkingV1Api',
            method='replace_namespaced_ingress'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='NetworkingV1Api',
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
            method='replace_namespaced_persistent_volume_claim'
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
            api='StorageV1Api',
            method='create_storage_class',
            payload='V1StorageClass'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='StorageV1Api',
            method='read_storage_class',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='StorageV1Api',
            method='patch_storage_class'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='StorageV1Api',
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
            method='replace_namespaced_config_map'
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
            method='replace_namespaced_secret'
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
            method='replace_namespaced_service_account'
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
            method='replace_namespaced_role'
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
            method='replace_namespaced_role_binding'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='RbacAuthorizationV1Api',
            method='delete_namespaced_role_binding',
            payload='V1DeleteOptions'
        ),
    ),
    'CustomResourceDefinition': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='ApiextensionsV1Api',
            method='create_custom_resource_definition',
            payload='V1CustomResourceDefinition'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='ApiextensionsV1Api',
            method='read_custom_resource_definition',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='ApiextensionsV1Api',
            method='patch_custom_resource_definition'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='ApiextensionsV1Api',
            method='delete_custom_resource_definition',
            payload='V1DeleteOptions'
        ),
    ),
    'CustomObjectsApi': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='CustomObjectsApi',
            method='create_namespaced_custom_object',
            payload=None,
        ),
        read=KubernetesSingleOperationApiMapping(
            api='CustomObjectsApi',
            method='get_namespaced_custom_object',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='CustomObjectsApi',
            method='replace_namespaced_custom_object',
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='CustomObjectsApi',
            method='delete_namespaced_custom_object',
            payload='V1DeleteOptions'
        ),
    ),
    'MutatingWebhookConfiguration': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='AdmissionregistrationV1Api',
            method='create_mutating_webhook_configuration',
            payload='V1MutatingWebhookConfiguration'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='AdmissionregistrationV1Api',
            method='read_mutating_webhook_configuration',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='AdmissionregistrationV1Api',
            method='patch_mutating_webhook_configuration'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='AdmissionregistrationV1Api',
            method='delete_mutating_webhook_configuration',
            payload='V1DeleteOptions'
        ),
    ),
    'ValidatingWebhookConfiguration': KubernetesApiMapping(
        create=KubernetesSingleOperationApiMapping(
            api='AdmissionregistrationV1Api',
            method='create_validating_webhook_configuration',
            payload='V1ValidatingWebhookConfiguration'
        ),
        read=KubernetesSingleOperationApiMapping(
            api='AdmissionregistrationV1Api',
            method='read_validating_webhook_configuration',
        ),
        update=KubernetesSingleOperationApiMapping(
            api='AdmissionregistrationV1Api',
            method='patch_validating_webhook_configuration'
        ),
        delete=KubernetesSingleOperationApiMapping(
            api='AdmissionregistrationV1Api',
            method='delete_validating_webhook_configuration',
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
