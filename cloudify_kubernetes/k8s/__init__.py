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

from .authentication import KubernetesApiAuthenticationVariants  # noqa
from .client import (KubernetesResourceDefinition, # noqa
                     CloudifyKubernetesClient) # noqa
from .config import KubernetesApiConfigurationVariants  # noqa
from .mapping import (get_mapping, # noqa
                      KubernetesApiMapping) # noqa
from .exceptions import (KuberentesError, # noqa
                         KuberentesApiInitializationFailedError,  # noqa
                         KuberentesApiOperationError,  # noqa
                         KuberentesAuthenticationError, # noqa
                         KuberentesInvalidDefinitionError, # noqa
                         KuberentesInvalidPayloadClassError,  # noqa
                         KuberentesInvalidApiClassError,  # noqa
                         KuberentesInvalidApiMethodError, # noqa
                         KuberentesMappingNotFoundError) # noqa

# Monkey Patch "V1beta1CustomResourceDefinitionStatus"
# https://github.com/kubernetes-client/python/issues/415
