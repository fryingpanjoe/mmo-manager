import logging
import json

LOG = logging.getLogger(__name__)


class Config(object):
    def __init__(self):
        self.__tree = {}

    def load(self, filename):
        LOG.info('loading mm.conf')
        with open(filename) as config_file:
            self.__tree.update(json.load(config_file))

    def get(self, *keys):
        node = self.__tree
        for key in keys:
            node = node[key]
        return node
