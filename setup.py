#!/usr/bin/env python3

import setuptools

from setuptools.command.sdist import sdist
from distutils.spawn import spawn


class CustomSdist(sdist):
    def run(self):
        spawn(["make"], dry_run=self.dry_run)
        super().run()


setuptools.setup(cmdclass={"sdist": CustomSdist})
