#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016-2018, Fabian Greif
# Copyright (c) 2018, Niklas Hauser
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import logging
import collections
import threading
from os.path import join, relpath, dirname, normpath, basename, isabs, abspath

import lxml.etree
from .exception import LbuildBuildException
import lbuild.utils

LOGGER = logging.getLogger('lbuild.buildlog')


class Operation:
    """
    Representation of a build operation.

    Stores the connection between a generated file and its template and module
    from within it was generated.
    """

    def __init__(self, module_name, outpath, module_path, filename_in: str, filename_out: str, time=None):
        self.module_name = module_name
        self.time = time

        self.outpath = abspath(outpath)
        self.inpath = abspath(module_path)

        self.filename_in = abspath(filename_in)
        self.filename_out = abspath(filename_out)

    def local_filename_in(self, relative_to=None):
        path = self.inpath
        if relative_to is not None:
            path = join(path, relative_to)
        return self._local_filename(self.filename_in, path)

    def local_filename_out(self, relative_to=None):
        path = self.outpath
        if relative_to is not None:
            path = join(path, relative_to)
        return self._local_filename(self.filename_out, path)

    @staticmethod
    def _local_filename(filename, path):
        localfile = join(relpath(dirname(filename), path), basename(filename))
        return normpath(localfile)

    def __repr__(self):
        return "<{}: {} -> {}>".format(self.module_name, self.filename_in, self.filename_out)


class BuildLog:
    """
    Log of a all files being generated during the build step.

    Used to detect if a previously generated file is being overwritten by
    another module. Also allow to later find out which module has generated
    a specific file.
    """

    def __init__(self, outpath):
        self._operations = collections.defaultdict(list)
        self._metadata = collections.defaultdict(lambda: collections.defaultdict(set))
        self.outpath = abspath(outpath)

        self._build_files = {}
        self.__lock = threading.RLock()

    def add_metadata(self, module, key, values):
        with self.__lock:
            for value in lbuild.utils.listify(values):
                self._metadata[key][module.fullname].add(value)

    @property
    def metadata(self):
        metadata = collections.defaultdict(set)
        for key, data in self._metadata.items():
            for value in data.values():
                metadata[key] |= value
        for key in metadata:
            metadata[key] = sorted(list(metadata[key]))
        return metadata

    @property
    def repo_metadata(self):
        metadata = collections.defaultdict(lambda: collections.defaultdict(set))
        for key, data in self._metadata.items():
            for module, value in data.items():
                metadata[key][module.split(":")[0]] |= value
        for key in metadata:
            for repo in metadata[key]:
                metadata[key][repo] = sorted(list(metadata[key][repo]))
        return metadata

    @property
    def module_metadata(self):
        metadata = collections.defaultdict(lambda: collections.defaultdict(set))
        for key, data in self._metadata.items():
            for module, value in data.items():
                metadata[key][module] |= value
        for key in metadata:
            for module in metadata[key]:
                metadata[key][module] = sorted(list(metadata[key][module]))
        return metadata

    def log(self, module, filename_in: str, filename_out: str, time=None):
        if not isabs(filename_in):
            filename_in = join(module._filepath, filename_in)
        if not isabs(filename_out):
            filename_out = join(self.outpath, filename_out)
        with self.__lock:
            operation = Operation(module.fullname, self.outpath, module._filepath, filename_in, filename_out, time)
            LOGGER.debug(str(operation))

            previous = self._build_files.get(filename_out, None)
            if previous is not None:
                raise LbuildBuildException(
                        "Overwrite file '{}' from '{}' (module '{}'). Previously "
                        "generated from '{}' (module '{}').".format(
                                filename_out, filename_in, module.fullname,
                                previous.filename_in, previous.module_name))

            self._build_files[filename_out] = operation
            self._operations[module.fullname].append(operation)

        return operation

    def _log(self, modulename, filename_in, filename_out, time=None):
        operation = Operation(modulename, self.outpath, self.outpath, filename_in, filename_out, time)
        with self.__lock:
            self._operations[modulename].append(operation)

    def operations_per_module(self, modulename: str):
        """
        Get all operations which have been performed for the given module and
        its submodules.

        Args:
            modulename: Full module name.
        """
        with self.__lock:
            operations = [self._operations.get(name, []) for name in self.modules
                                                   if name.startswith(modulename)]
        operations = [o for olists in operations for o in olists]
        return sorted(operations, key=lambda o: (o.module_name, o.filename_in, o.filename_out))

    @property
    def modules(self):
        with self.__lock:
            module_names = self._operations.keys()
        return list(module_names)

    @property
    def operations(self):
        with self.__lock:
            operations = self._operations.values()
        operations = [o for olists in operations for o in olists]
        return sorted(operations, key=lambda o: (o.module_name, o.filename_in, o.filename_out))

    @staticmethod
    def from_xml(string, path):
        rootnode = lxml.etree.fromstring(string)
        outpath = join(abspath(path), rootnode.find("outpath").text)
        buildlog = BuildLog(outpath)

        for opnode in rootnode.iterfind("operation"):
            module_name = opnode.find("module").text
            source = join(outpath, opnode.find("source").text)
            destination = join(outpath, opnode.find("destination").text)
            operation = Operation(module_name, outpath, path, source, destination)
            buildlog._operations[module_name].append(operation)

        return buildlog

    def to_xml(self, path, to_string=True):
        """
        Convert the complete build log into a XML representation.
        """
        rootnode = lxml.etree.Element("buildlog")

        with self.__lock:
            outpathnode = lxml.etree.SubElement(rootnode, "outpath")
            outpathnode.text = relpath(self.outpath, path)
            for operation in self.operations:
                operationnode = lxml.etree.SubElement(rootnode, "operation")

                modulenode = lxml.etree.SubElement(operationnode, "module")
                modulenode.text = operation.module_name
                srcnode = lxml.etree.SubElement(operationnode, "source")
                srcnode.text = relpath(operation.filename_in, path)
                destnode = lxml.etree.SubElement(operationnode, "destination")
                destnode.text = relpath(operation.filename_out, path)

                if operation.time is not None:
                    timenode = lxml.etree.SubElement(operationnode, "time")
                    timenode.text = "{:.3f} ms".format(operation.time * 1000)

        if to_string:
            return lxml.etree.tostring(rootnode,
                                       encoding="UTF-8",
                                       pretty_print=True,
                                       xml_declaration=True,)
        else:
            return rootnode
