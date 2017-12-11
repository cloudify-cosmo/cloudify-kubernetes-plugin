import sys
import imp
import os

class OurImporter(object):

    def __init__(self, dir_name, load_file, name):
        print ("importer:{}/{}".format(repr(dir_name), repr(load_file)))
        self.dirname = dir_name
        self.load_file = load_file
        self.file_name = name

    def load_module(self, fullname):
        print ("load_module:{}".format(repr(fullname)))
        try:
            return sys.modules[fullname]
        except KeyError:
            pass
        print("--- load ---")
        print(fullname)
        if self.load_file:
            print (self.dirname + "/__init__.py")
            with open(self.dirname + "/__init__.py") as module_file:
                m = imp.load_source(fullname, self.dirname + "/" + self.file_name, module_file)
        else:
            m = imp.new_module(fullname)
            m.__name__ = fullname
            m.__file__ = self.dirname + "/" + self.file_name
            m.__path__ = [self.dirname]
            m.__loader__ = self
            print (m.__path__)

        sys.modules.setdefault(fullname, m)

        print (m.__file__)
        print (m.__name__)
        return m

class OurFinder(object):

    def __init__(self, dir_name):
        print ("finder:{}".format(repr(dir_name)))

    def find_module(self, package_name):
        print ("find_module:{}".format(repr(package_name)))
        real_path = "/".join(package_name.split("."))
        for path in sys.path:
            if path[:len("/usr")] == "/usr":
                 continue

            if not os.path.isfile(path + "/" + package_name.split(".")[0]  + "/" + "__init__.py"):
                full_name = path + "/" + real_path

                if os.path.isfile(full_name + ".py"):
                    print ">>>>" + full_name + ".py"
                    return OurImporter(full_name, True, package_name.split(".")[-1] + ".py")
                if os.path.isdir(full_name):
                    if not os.path.isfile(full_name  + "/" + "__init__.py"):
                        print "Is namespaced package: {}".format(path)
                        return OurImporter(full_name, False, "__init__.py")
                    else:
                        return OurImporter(full_name, True, "__init__.py")
        return None


def check_import(dir_name):
    print ("check_import:{}".format(repr(dir_name)))
    return OurFinder(dir_name)

sys.path_hooks.append(check_import)
sys.path.append("../lib/python2.7/site-packages")

import google.auth

import datetime

print  google.auth.__all__

#import google
#print google.__path__ # ['.../lib/python2.7/site-packages/google', '.../lib/python2.7/site-packages/google']
#print google.__name__ # "google"

#print google.auth.__path__ # ['.../lib/python2.7/site-packages/google/auth']
#print google.auth.__name__ # "google.auth"
