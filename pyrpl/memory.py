import os
import yaml
from collections import OrderedDict
from shutil import copyfile

import logging
logger = logging.getLogger(name=__name__)

# ordered load and dump for yaml files. From
# http://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
def ordered_load(stream, Loader=yaml.Loader, object_pairs_hook=OrderedDict):
    class OrderedLoader(Loader):
        pass
    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load(stream, OrderedLoader)

def ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwds):
    class OrderedDumper(Dumper):
        pass
    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())
    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)

# usage example:
# ordered_load(stream, yaml.SafeLoader)
# ordered_dump(data, Dumper=yaml.SafeDumper)

class MemoryBranch(object):
    """Represents a branch of a memoryTree"""
    def __init__(self, parent, branch):
        self._branch = branch
        self._parent = parent
        self.__dict__.update(self._data)

    @property
    def _data(self):
        return self._parent._data[self._branch]

    def _reload(self):
        self._parent._reload()

    def _save(self):
        self._parent._save()

    def __getattribute__(self, name):
        if name.startswith('_') or name not in self._data:
            return super(MemoryBranch, self).__getattribute__(name)
        else:
            # make sure data is up-to-date
            self._reload()
            # if subbranch, return MemoryBranch object
            if type(self._data[name]) == OrderedDict:
                # test if we have a LemoryLeaf
                if 'value' in self._data[name]:
                    return self._data[name]['value']
                    #return MemoryLeaf(self, name)
                # otherwise create a MemoryBranch object
                else:
                    return MemoryBranch(self, name)
            else:
                return self._data[name]

    def __setattr__(self, name, value):
        if name.startswith('_') or name not in self._data:
            super(MemoryBranch, self).__setattr__(name, value)
        else:
            if type(self._data[name]) == OrderedDict and 'value' in self._data[name]:
                ro = self._data[name]["ro"] or False
                if ro:
                    logger.info("Attribute %s is read-only. New value %s cannot be written to config file",
                                name, value)
                else:
                    self._data[name]['value'] = value
            else:
                self._data[name] = value
            self._save()

class MemoryTree(MemoryBranch):
    _data = OrderedDict()

    def __init__(self, filename):
        if os.path.isfile(filename):
            self._filename = filename
        else:
            logger.warning("File "+filename+" not found. New file created. ")
            self._filename = filename
            with open(self._filename, mode="w") as f:
                pass
        self._load()
        self._branch = ""
        self._parent = self

    def _load(self):
        with open(self._filename) as f:
            self._data = ordered_load(f, Loader=yaml.SafeLoader)
        # update dict of the object
        for name in self.__dict__:
            if not name.startswith('_') and name not in self._data:
                self.__dict__.pop(name)
        self.__dict__.update(self._data)
        self._mtime = os.path.getmtime(self._filename)

    def _reload(self):
        if self._mtime != os.path.getmtime(self._filename):
            logger.debug("Reloading config file %s", self._filename)
            self._load()

    def _save(self):
        if self._mtime != os.path.getmtime(self._filename):
            logger.warning("Config file has recently been changed. These "\
                           +"changes might have been overwritten now.")
        logger.debug("Saving config file %s", self._filename)
        copyfile(self._filename,self._filename+".bak")
        try:
            f = open(self._filename, mode='w')
            ordered_dump(self._data, stream=f, Dumper=yaml.SafeDumper, default_flow_style=False)
            f.close()
        except:
            copyfile(self._filename+".bak",self._filename)
            logger.error("Error writing to file. Backup version was restored.")
