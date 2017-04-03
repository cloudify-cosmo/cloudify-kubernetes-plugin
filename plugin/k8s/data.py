class KubernetesResourceDefinition(object):

    def __init__(self, kind, apiVersion, metadata, spec):
        self.kind = kind.split('.')[-1]
        self.api_version = apiVersion
        self.metadata = metadata
        self.spec = spec


class KubernetesApiMapping(object):

    def __init__(self, create, read, delete):
        self.create = create
        self.read = read
        self.delete = delete
