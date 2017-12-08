import sys

class OurImporter(object):

    def __init__(self, dir_name):
        print ("load_module:{}".format(repr(dir_name)))

    def load_module(self, *argv, **kwargs):
        print ("load_module:{}".format(repr(kwargs)))
        print ("load_module:{}".format(repr(argv)))
        print ("load_module:{}".format(repr(sys.path)))
        raise ImportError()

    def find_module(self, *argv, **kwargs):
        print ("find_module:{}".format(repr(kwargs)))
        print ("find_module:{}".format(repr(argv)))
        print ("find_module:{}".format(repr(sys.path)))
        raise ImportError()

    def iter_module(self, *argv, **kwargs):
        print ("iter_module:{}".format(repr(kwargs)))
        print ("iter_module:{}".format(repr(argv)))
        print ("iter_module:{}".format(repr(sys.path)))
        raise ImportError()

def check_import(dir_name):
    print ("check_import:{}".format(repr(dir_name)))
    return OurImporter(dir_name)

sys.path_hooks.append(check_import)

import google.auth
