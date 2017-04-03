class KuberentesError(Exception):
    pass


class KuberentesApiInitializationFailedError(KuberentesError):
    pass


class KuberentesApiOperationError(KuberentesError):
    pass


class KuberentesInvalidPayloadClassError(KuberentesError):
    pass


class KuberentesInvalidApiClassError(KuberentesError):
    pass


class KuberentesInvalidApiMethodError(KuberentesError):
    pass
