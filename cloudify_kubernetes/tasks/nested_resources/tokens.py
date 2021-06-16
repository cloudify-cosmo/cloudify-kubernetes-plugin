# Copyright (c) 2017-2021 Cloudify Platform Ltd. All rights reserved
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
SERVICE_ACCOUNT = """{{
    'apiVersion': 'v1',
    'kind': 'ServiceAccount',
    'metadata': {{
        'name': {service_account_name},
        'namespace': {service_account_namespace}
    }}
}}"""

CLUSTER_ROLE_BINDING = """{{
    'apiVersion': 'rbac.authorization.k8s.io/v1',
    'kind': 'ClusterRoleBinding',
    'metadata': {{
        'name': {service_account_name}
    }},
    'roleRef': {{
        'apiGroup': 'rbac.authorization.k8s.io',
        'kind': 'ClusterRole',
        'name': 'cluster-admin'
    }},
    'subjects': [
        {{
            'kind': 'ServiceAccount',
            'name': {service_account_name},
            'namespace': {service_account_namespace}
        }}
    ]
}}"""

SECRET = """{{
    'apiVersion': 'v1',
    'kind': 'Secret',
    'metadata': {{
        'name': {secret_name}
    }}
}}"""


def get_service_account_payload(name, namespace):
    return SERVICE_ACCOUNT.format(
        service_account_name=name,
        service_account_namespace=namespace
    )


def get_cluster_role_binding_payload(name, namespace):
    return CLUSTER_ROLE_BINDING.format(
        service_account_name=name,
        service_account_namespace=namespace
    )


def get_secret_payload(name):
    return SECRET.format(secret_name=name)
