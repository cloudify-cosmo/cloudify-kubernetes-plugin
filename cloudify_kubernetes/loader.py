# #######
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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import sys
import imp
import os
from cloudify import ctx


class OurImporter(object):

    def __init__(self, dir_name, load_file, name):
        ctx.logger.info("importer:{}/{}".format(dir_name, load_file))
        self.dirname = dir_name
        self.load_file = load_file
        self.file_name = name

    def load_module(self, package_name):
        ctx.logger.info("load_module: {}".format(package_name))
        try:
            return sys.modules[package_name]
        except KeyError:
            pass

        if self.load_file:
            fp, pathname, description = imp.find_module(
                package_name.split(".")[-1],
                ["/".join(os.path.abspath(self.dirname).split("/")[:-1])]
            )
            m = imp.load_module(package_name, fp, pathname, description)
        else:
            m = imp.new_module(package_name)

            m.__name__ = package_name
            m.__path__ = [os.path.abspath(self.dirname)]
            m.__doc__ = None

        sys.modules.setdefault(package_name, m)
        return m


class _OurFinder(object):

    def __init__(self, dir_name):
        ctx.logger.info("finder:\t{}".format(dir_name))

    def find_module(self, package_name):
        real_path = "/".join(package_name.split("."))
        for path in sys.path:

            full_name = path + "/" + real_path

            if os.path.isfile(path + "/" + real_path + ".py"):
                return OurImporter(os.path.abspath(full_name),
                                   True, "__init__.py")
            elif not os.path.isfile(
                path + "/" + package_name.split(".")[0] + "/" + "__init__.py"
            ):
                if os.path.isdir(full_name):
                    if not os.path.isfile(full_name + "/" + "__init__.py"):
                        return OurImporter(
                            os.path.abspath(full_name), False, "__init__.py")
                    else:
                        return OurImporter(
                            os.path.abspath(full_name), True, "__init__.py")
        return None


def _check_import(dir_name):
    return _OurFinder(dir_name)


def register_callback():
    sys.path_hooks.append(_check_import)
