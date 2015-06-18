#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import os
import sys
import unittest
import testfixtures

# Hack to support the usage of `coverage`
sys.path.append(os.path.abspath("."))

import lbuild

class ParserTest(unittest.TestCase):
    
    def _getPath(self, filename):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), filename)
    
    def setUp(self):
        self.parser = lbuild.parser.Parser()
    
    def test_shouldParseRepository1(self):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        self.assertEqual(1, len(self.parser.repositories))
    
    def test_shouldFindFilesInRepository1(self):
        repo = self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        
        self.assertEqual(3, len(repo.modules))
        self.assertIn(self._getPath("resources/repo1/other.lb"), repo.modules)
        self.assertIn(self._getPath("resources/repo1/module1/module.lb"), repo.modules)
        self.assertIn(self._getPath("resources/repo1/module2/module.lb"), repo.modules)

    def test_shouldFindFilesInRepository2(self):
        repo = self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
        self.assertEqual(1, len(self.parser.repositories))
        
        self.assertEqual(4, len(repo.modules))
        self.assertIn(self._getPath("resources/repo2/module3/module.lb"), repo.modules)
        self.assertIn(self._getPath("resources/repo2/module4/module.lb"), repo.modules)
        self.assertIn(self._getPath("resources/repo2/module4/submodule1/module.lb"), repo.modules)
        self.assertIn(self._getPath("resources/repo2/module4/submodule2/module.lb"), repo.modules)

    def testRepository2HasOptions(self):
        repo = self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
        
        self.assertIn("target", repo.options)
        self.assertIn("include_tests", repo.options)
        
        self.assertEqual(True, repo.options["include_tests"].value)

    def test_shouldParseModules(self):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        
        self.assertEqual(3, len(self.parser.modules))
        self.assertIn("repo1:module1", self.parser.modules)
        self.assertIn("repo1:module2", self.parser.modules)
        self.assertIn("repo1:other", self.parser.modules)

    def test_shouldParseModulesFromMultipleRepositories(self):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
        
        self.assertEqual(7, len(self.parser.modules))
        self.assertIn("repo1:module1", self.parser.modules)
        self.assertIn("repo1:module2", self.parser.modules)
        self.assertIn("repo1:other", self.parser.modules)
        self.assertIn("repo2:module3", self.parser.modules)
        self.assertIn("repo2:module4", self.parser.modules)
        self.assertIn("repo2:module4.submodule1", self.parser.modules)
        self.assertIn("repo2:module4.submodule2", self.parser.modules)
    
    def test_shouldParseConfigurationFile(self):
        modules, options = self.parser.parse_configuration(self._getPath("resources/test1.lb"))
        
        self.assertEqual(2, len(modules))
        self.assertIn("repo1:other", modules)
        self.assertIn(":module1", modules)
        
        self.assertEqual(6, len(options))
        self.assertEqual('hosted', options[':target'])
        self.assertEqual('43', options['repo1:foo'])
        
        self.assertEqual('456', options['repo1:other:foo'])
        self.assertEqual('768', options['repo1::bar'])
        self.assertEqual('No', options[':other:xyz'])
        self.assertEqual('Hello World!', options['::abc'])

    def test_shouldMergeOptions(self):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
        _, config_options = self.parser.parse_configuration(self._getPath("resources/test1.lb"))
        
        options = self.parser.merge_repository_options(config_options)
        self.assertEqual("hosted", options["repo1:target"].value)
        self.assertEqual(43, options["repo1:foo"].value)
        self.assertEqual("hosted", options["repo2:target"].value)
        self.assertEqual(True, options["repo2:include_tests"].value)
    
    def test_shouldSelectAvailableModules(self):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        _, config_options = self.parser.parse_configuration(self._getPath("resources/test1.lb"))
        
        options = self.parser.merge_repository_options(config_options)
        modules = self.parser.prepare_modules(options)
        
        self.assertIn("repo1:other", modules)
        self.assertIn("repo1:module1", modules)
    
    def _get_build_modules(self):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
        selected_modules, config_options = self.parser.parse_configuration(self._getPath("resources/test1.lb"))
        
        repo_options = self.parser.merge_repository_options(config_options)
        modules = self.parser.prepare_modules(repo_options)
        build_modules = self.parser.resolve_dependencies(modules, selected_modules)
        
        return build_modules, config_options, repo_options
      
    def test_shouldResolveModuleDependencies(self):
        build_modules, _, _ = self._get_build_modules()
        
        self.assertEqual(3, len(build_modules))
        
        m = [x.full_name for x in build_modules]
        self.assertIn("repo1:other", m)
        self.assertIn("repo1:module1", m)
        self.assertIn("repo2:module4", m)

    def test_shouldMergeBuildModuleOptions(self):
        build_modules, config_options, _ = self._get_build_modules()
        options = self.parser.merge_module_options(build_modules, config_options)
        
        self.assertEqual(4, len(options))
        self.assertEqual(456, options["repo1:other:foo"].value)
        self.assertEqual(768, options["repo1:other:bar"].value)
        self.assertEqual(False, options["repo1:other:xyz"].value)
        self.assertEqual("Hello World!", options["repo1:other:abc"].value)

    @testfixtures.tempdir()
    def test_shouldBuildModules(self, tempdir):
        build_modules, config_options, repo_options = self._get_build_modules()
        module_options = self.parser.merge_module_options(build_modules, config_options)
        
        outpath = tempdir.path
        self.parser.build_modules(outpath, build_modules, repo_options, module_options)
        
        self.assertTrue(os.path.isfile(os.path.join(outpath, "src/other.cpp")))
        self.assertTrue(os.path.isfile(os.path.join(outpath, "test/other.cpp")))
    
    @testfixtures.tempdir()
    def test_shouldBuildJinja2Modules(self, tempdir):
        self.parser.parse_repository(self._getPath("resources/repo1.lb"))
        self.parser.parse_repository(self._getPath("resources/repo2/repo2.lb"))
        
        selected_modules = ["repo2:module3"]
        config_options = {
            ':target': 'hosted',
            ':other:xyz': 'No',
            'repo1::bar': '768',
            'repo1:other:foo': '456',
            '::abc': 'Hello World!',
        }
        
        repo_options = self.parser.merge_repository_options(config_options)
        modules = self.parser.prepare_modules(repo_options)
        build_modules = self.parser.resolve_dependencies(modules, selected_modules)
        module_options = self.parser.merge_module_options(build_modules, config_options)
        
        outpath = tempdir.path
        self.parser.build_modules(outpath, build_modules, repo_options, module_options)
        
        self.assertTrue(os.path.isfile(os.path.join(outpath, "src/module3.cpp")))
        
        testfixtures.compare(tempdir.read("src/module3.cpp"), b"Hello World!")

if __name__ == '__main__':
    unittest.main()
