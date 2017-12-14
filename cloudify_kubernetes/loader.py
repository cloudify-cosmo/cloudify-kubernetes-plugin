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
import time

STAMP = str(time.time())


class _OurImporter(object):

    def __init__(self, dir_name, load_file):
        self.dirname = dir_name
        self.load_file = load_file

    def load_module(self, package_name):
        with open("/tmp/import" + STAMP + ".log", 'a+') as file:
            file.write("import {} by {} as file: {}\n".format(
                repr(package_name), repr(self.dirname), repr(self.load_file)
            ))

        try:
            return sys.modules[package_name]
        except KeyError:
            pass

        if self.load_file:
            try:
                fp, pathname, description = imp.find_module(
                    package_name.split(".")[-1],
                    ["/".join(os.path.abspath(self.dirname).split("/")[:-1])]
                )
                m = imp.load_module(package_name, fp, pathname, description)
            except ImportError as e:
                with open("/tmp/import" + STAMP + ".log", 'a+') as file:
                   file.write("Failed {}, reason {}\n"
                              .format(repr(package_name), repr(e)))
                raise e
        else:
            m = imp.new_module(package_name)

            m.__name__ = package_name
            m.__path__ = [os.path.abspath(self.dirname)]
            m.__doc__ = None

        m.__loader__ = self

        sys.modules.setdefault(package_name, m)
        return m


class _OurFinder(object):

    def __init__(self, dir_name):
        self.dir_name = os.path.abspath(dir_name)

    def find_module(self, package_name):
        with open("/tmp/import" + STAMP + ".log", 'a+') as file:
            file.write("import {} from {}\n".format(
                repr(package_name), repr(self.dir_name)
            ))

        real_path = "/".join(package_name.split("."))

        for path in [self.dir_name] + sys.path:

            full_name = path + "/" + real_path

            if os.path.isfile(path + "/" + real_path + ".py"):
                return _OurImporter(os.path.abspath(full_name), True)

            if os.path.isdir(full_name):
                if not os.path.isfile(full_name + "/" + "__init__.py"):
                    return _OurImporter(os.path.abspath(full_name), False)

                return _OurImporter(os.path.abspath(full_name), True)

        return None


def _check_import(dir_name):
    with open("/tmp/import" + STAMP + ".log", 'a+') as file:
        file.write("import from {} with sys.path: {}\n".format(
            repr(dir_name), repr(sys.path)
        ))
    return _OurFinder(dir_name)


def register_callback():
    sys.path_hooks.append(_check_import)
    import google.auth
