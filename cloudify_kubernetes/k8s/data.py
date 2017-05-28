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
