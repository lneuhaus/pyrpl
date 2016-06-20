###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2016  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################

import os
from collections import OrderedDict
from shutil import copyfile

import logging
logger = logging.getLogger(name=__name__)

try:
    import ruamel.yaml
    def load(f):
        return ruamel.yaml.load(f, ruamel.yaml.RoundTripLoader)
    def save(data, stream=None  ):
        return ruamel.yaml.dump(data, stream=stream, Dumper=ruamel.yaml.RoundTripDumper, default_flow_style = False)
    def isbranch(obj):
        return isinstance(obj, OrderedDict) #type is ruamel.yaml.comments.CommentedMap
except:
    logger.warning("ruamel.yaml could not be found. Using yaml instead. Comments in config files will be lost.")
    import yaml
    # ordered load and dump for yaml files. From
    # http://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
    def load(stream, Loader=yaml.SafeLoader, object_pairs_hook=OrderedDict):
        class OrderedLoader(Loader):
            pass
        def construct_mapping(loader, node):
            loader.flatten_mapping(node)
            return object_pairs_hook(loader.construct_pairs(node))
        OrderedLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            construct_mapping)
        return yaml.load(stream, OrderedLoader)
    def save(data, stream=None, Dumper=yaml.SafeDumper, default_flow_style=False, **kwds):
        class OrderedDumper(Dumper):
            pass
        def _dict_representer(dumper, data):
            return dumper.represent_mapping(
                yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                data.items())
        OrderedDumper.add_representer(OrderedDict, _dict_representer)
        return yaml.dump(data, stream, OrderedDumper,
                         default_flow_style=default_flow_style, **kwds)
    def isbranch(obj):
        return type(obj) == OrderedDict
    # usage example:
    # load(stream, yaml.SafeLoader)
    # save(data, stream=f, Dumper=yaml.SafeDumper)

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
            if isbranch(self._data[name]):
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
            if isbranch(self._data[name]) and 'value' in self._data[name]:
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
            self._data = load(f)
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
            save(self._data, stream=f)
            f.close()
        except:
            copyfile(self._filename+".bak",self._filename)
            logger.error("Error writing to file. Backup version was restored.")
