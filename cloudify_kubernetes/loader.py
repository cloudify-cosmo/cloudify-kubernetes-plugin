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
import __builtin__


class _OurImporter(object):

    def __init__(self, dir_name, load_file):
        self.dirname = dir_name
        self.load_file = load_file

    def load_module(self, package_name):
        try:
            return sys.modules[package_name]
        except KeyError:
            pass

        if self.load_file:
            try:
                fp, pathname, description = imp.find_module(
                    package_name.split(".")[-1],
                    ["/".join(self.dirname.split("/")[:-1])]
                )
                m = imp.load_module(package_name, fp, pathname, description)
            except ImportError as e:
                raise e
        else:
            m = imp.new_module(package_name)

            m.__name__ = package_name
            m.__path__ = [self.dirname]
            m.__doc__ = None

        m.__loader__ = self

        sys.modules.setdefault(package_name, m)
        return m


class _OurFinder(object):

    def __init__(self, dir_name):
        self.dir_name = dir_name

    def find_module(self, package_name):
        real_path = "/".join(package_name.split("."))

        for path in [self.dir_name] + sys.path:

            full_name = os.path.abspath(path) + "/" + real_path
            dir_root = os.path.abspath(path) + "/" + real_path.split("/")[0]

            if os.path.isfile(path + "/" + real_path + ".py"):
                return _OurImporter(full_name, True)

            if os.path.isdir(full_name):
                if not os.path.isfile(dir_root + "/" + "__init__.py"):
                    with open(dir_root + "/" + "__init__.py", 'a+') as file:
                        file.write("# Created by importer")
                    return _OurImporter(dir_root, False)

                return _OurImporter(full_name, True)

        return None


def _check_import(dir_name):
    return _OurFinder(dir_name)


def register_callback():
    sys.path_hooks.append(_check_import)

    save_import = __builtin__.__import__

    def new_import(*argv, **kwargs):
        try:
            module = save_import(*argv, **kwargs)
        except ImportError as e:
            finder = _OurFinder("")
            if not finder:
                raise e
            importer = finder.find_module(argv[0])
            if not importer:
                raise e
            module = importer.load_module(argv[0])
            if not module:
                raise e

        return module

    __builtin__.__import__ = new_import
