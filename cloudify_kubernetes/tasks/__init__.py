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

# The cloudify_kubernetes.tasks module has really got out of control.
from .._compat import PY2
if not PY2:
    from .shared_cluster import refresh_config  # noqa
from .operations import (read_token,  # noqa
                         create_token,  # noqa
                         delete_token,  # noqa
                         resource_read,  # noqa
                         resource_create,  # noqa
                         resource_update,  # noqa
                         resource_delete,  # noqa
                         file_resource_read,  # noqa
                         file_resource_create,  # noqa
                         file_resource_update,  # noqa
                         file_resource_delete,  # noqa
                         custom_resource_create,  # noqa
                         custom_resource_update,  # noqa
                         custom_resource_delete,  # noqa
                         multiple_file_resource_read,  # noqa
                         multiple_file_resource_create,  # noqa
                         multiple_file_resource_delete )   # noqa
from .api_calls import (_do_resource_read,  # noqa
                        _do_resource_create,  # noqa
                        _do_resource_update,  # noqa
                        _do_resource_status_check,  # noqa
                        _do_resource_delete)  # noqa
