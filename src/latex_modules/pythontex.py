# This file is part of Rubber and thus covered by the GPL
# (c) Ferdinand Schwenk, 2013
# (c) Sebastian Kapfer 2015
# vim: noet:ts=4
"""
pythontex support for Rubber
"""

from rubber.util import _
import logging
msg = logging.getLogger (__name__)
import os.path
import shutil
import rubber.module_interface

class PythonTeXDep (rubber.depend.Shell):

    def __init__ (self, document):
        self.doc = document
        basename = self.doc.basename ()
        super ().__init__ (('pythontex', basename))
        self.pythontex_files = 'pythontex-files-' + basename

        pytxcode = basename + '.pytxcode'
        self.doc.add_product (pytxcode)
        self.add_source (pytxcode)

        pytxmcr = os.path.join (self.pythontex_files, basename + '.pytxmcr')
        self.add_product (pytxmcr)
        self.doc.add_source (pytxmcr)

    def run (self):
        if not self.doc.env.is_in_unsafe_mode_:
            msg.error (_('The document tries to run embedded Python code which could be dangerous.  Use rubber --unsafe if the document is trusted.'))
            return False
        return super (PythonTeXDep, self).run ()

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):
        self.dep = PythonTeXDep (document)

    def clean (self):
        trash = self.dep.pythontex_files
        msg.info (_("removing tree %s"), trash)
        # FIXME proper error reporting
        shutil.rmtree (trash, ignore_errors=True)
