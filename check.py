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
        print ("load_module: {}".format(repr(fullname)))
        try:
            return sys.modules[fullname]
        except KeyError:
            pass

        if self.load_file:
            m = imp.load_source(fullname, self.dirname + "/" + self.file_name)
        else:
            m = imp.new_module(fullname)

            m.__name__ = fullname
            m.__path__ = [os.path.abspath(self.dirname)]
            m.__doc__ = None

        sys.modules.setdefault(fullname, m)

        print ("name:\t" + repr(m.__name__))
        print ("path:\t" + repr(m.__path__))
        return m

class OurFinder(object):

    def __init__(self, dir_name):
        print ("finder:\t{}".format(repr(dir_name)))

    def find_module(self, package_name):
        print ("find_module: {}".format(repr(package_name)))
        real_path = "/".join(package_name.split("."))
        for path in sys.path:
            if path[:len("/usr")] == "/usr":
                 continue

            if not os.path.isfile(path + "/" + package_name.split(".")[0]  + "/" + "__init__.py"):
                full_name = path + "/" + real_path

                if os.path.isdir(full_name):
                    if not os.path.isfile(full_name  + "/" + "__init__.py"):
                        print "Is namespaced package!: {}".format(path)
                        return OurImporter(os.path.abspath(full_name), False, "__init__.py")
                    else:
                        try:
                             fp, pathname, description =  imp.find_module(package_name.split(".")[-1], ["/".join(os.path.abspath(full_name).split("/")[:-1])])
                             print repr(imp.load_module(package_name, fp, pathname, description))
                        except Exception as e:
                             print repr(e)
                        return None
                        # return OurImporter(os.path.abspath(full_name), True, "__init__.py")
        return None


def check_import(dir_name):
    return OurFinder(dir_name)

sys.path_hooks.append(check_import)
sys.path.append("../lib/python2.7/site-packages")

import google.auth

#import datetime

#print  google.auth.__all__

import google
print google.__path__ # ['.../lib/python2.7/site-packages/google', '.../lib/python2.7/site-packages/google']
print google.__name__ # "google"

#print google.auth.__path__ # ['.../lib/python2.7/site-packages/google/auth']
#print google.auth.__name__ # "google.auth"
