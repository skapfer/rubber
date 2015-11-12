# This file is part of Rubber and thus covered by the GPL
# (c) Ferdinand Schwenk, 2013
# (c) Sebastian Kapfer 2015
# vim: noet:ts=4
"""
pythontex support for Rubber
"""

from rubber import _, msg

import os.path

import rubber.module_interface
import rubber.util

class PythonTeXDep (rubber.depend.Shell):
	def __init__ (self, set, document):
		self.doc = document
		self.tool = 'pythontex'
		basename = self.doc.basename ()
		super (PythonTeXDep, self).__init__ (set, [self.tool, basename ])
		self.pytxcode = basename + '.pytxcode'
		self.pythontex_files = 'pythontex-files-%s/' % basename
		self.pytxmcr = self.pythontex_files + basename + '.pytxmcr'

		self.doc.add_product (self.pytxcode)
		self.add_source (self.pytxcode, track_contents=True)
		self.add_product (self.pytxmcr)
		self.doc.add_source (self.pytxmcr)

	def run (self):
		# check if the input file exists. if not, refuse to run.
		if not os.path.exists (self.sources[0]):
			msg.info (_('input file for %s does not yet exist, deferring')
				% self.tool, pkg='pythontex')
			return True
		if not self.doc.env.is_in_unsafe_mode_:
			msg.error (_('The document tries to run embedded Python code which could be dangerous.  Use rubber --unsafe if the document is trusted.'))
			return False
		return super (PythonTeXDep, self).run ()

	def clean (self):
		rubber.util.verbose_rmtree (self.pythontex_files)
		return super (PythonTeXDep, self).clean ()

class Module (rubber.module_interface.Module):
	def __init__ (self, document, context):
		PythonTeXDep (document.set, document)
