import json


class Config(object):
    def __init__(self):
        self.__tree = {}

    def load(self, filename):
        with open(filename) as config_file:
            self.__tree.update(json.load(config_file))

    def get(self, **keys):
        #node_key = ''
        #for key in keys:
            #node_key += key
