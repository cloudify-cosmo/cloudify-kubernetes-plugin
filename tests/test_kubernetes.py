import os
import re

from ecosystem_tests import (
    IP_ADDRESS_REGEX,
    EcosystemTestBase,
    utils as eco_utils)

KUBERNETES_BLUEPRINT_URL = 'https://github.com/cloudify-examples/' \
                           'simple-kubernetes-blueprint' \
                           '/archive/master.zip'


class KubernetesTestBase(EcosystemTestBase):

    @classmethod
    def tearDownClass(cls):
        eco_utils.execute_uninstall('k8s')
        try:
            del os.environ['KUBERNETES_MASTER_IP']
        except KeyError:
            pass
        eco_utils.execute_command(
            'cfy profiles delete {0}'.format(
                os.environ['ECOSYSTEM_SESSION_MANAGER_IP']))
        super(KubernetesTestBase, cls).tearDownClass()

    def setUp(self):
        super(KubernetesTestBase, self).setUp()
        if 'KUBERNETES_MASTER_IP' not in os.environ:
            os.environ['KUBERNETES_MASTER_IP'] = \
                self.get_kubernetes_master_ip()

    @property
    def plugins_to_upload(self):
        """plugin yamls to upload to manager"""
        return []

    @property
    def sensitive_data(self):
        return [
            os.environ['GCP_CERT_URL'],
            os.environ['GCP_EMAIL'],
            os.environ['GCP_CLIENT_ID'],
            os.environ['GCP_PRIVATE_PROJECT_ID'],
            os.environ['GCP_PRIVATE_KEY_ID'],
            os.environ['GCP_PRIVATE_KEY'],
            os.environ['GCP_PRIVATE_KEY'].decode('string_escape')
        ]
    
    @property
    def node_type_prefix(self):
        return 'cloudify.kubernetes.resources'

    @property
    def plugin_mapping(self):
        return 'kubernetes'

    @property
    def blueprint_file_name(self):
        return 'gcp.yaml'

    @property
    def external_id_key(self):
        return 'natIP'

    @property
    def server_ip_property(self):
        return 'cloudify_host'

    @property
    def inputs(self):
        try:
            return {
                'password': self.password,
                'region': 'asia-south1',
                'zone': 'asia-south1-b',
                'resource_prefix': 'k8s-'.format(self.application_prefix),
                'client_x509_cert_url': os.environ['GCP_CERT_URL'],
                'client_email': os.environ['GCP_EMAIL'],
                'client_id': os.environ['GCP_CLIENT_ID'],
                'project_id': os.environ['GCP_PRIVATE_PROJECT_ID'],
                'private_key_id': os.environ['GCP_PRIVATE_KEY_ID'],
                'private_key':
                    os.environ['GCP_PRIVATE_KEY'].decode('string_escape'),
            }
        except KeyError:
            raise

    def get_manager_ip(self):
        for instance in self.node_instances:
            if instance.node_id == self.server_ip_property:
                props = instance.runtime_properties
                nic = props['networkInterfaces'][0]
                return nic['accessConfigs'][0][self.external_id_key]
        raise Exception('No manager IP found.')

    def get_kubernetes_master_ip(self):
        pattern = re.compile(IP_ADDRESS_REGEX)
        response = eco_utils.get_secrets('kubernetes_master_ip')
        value = response['value']
        if pattern.match(value):
            return value
        failed = eco_utils.install_nodecellar(
            self.blueprint_file_name,
            {},
            KUBERNETES_BLUEPRINT_URL,
            'k8s'
        )
        if failed:
            raise Exception('Failed to install Kubernetes.')
        response = eco_utils.get_secrets(
            'kubernetes_master_ip')
        value = response['value']
        if not pattern.match(value):
            raise Exception('Kubernetes IP is: {0}'.format(value))
        return value

    def test_wordpress(self):
        failed = eco_utils.execute_command(
            'cfy install examples/wordpress-blueprint.yaml -b wp')
        if failed:
            raise Exception(
                'Failed to install wordpress blueprint.')
        del failed
