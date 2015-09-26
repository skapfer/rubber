# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# vim: noet:ts=4
"""
BibTeX support for Rubber

This module is a special one: it is triggered by the macros \\bibliography and
\\bibliographystyle and not as a package, so the main system knows about it.
The module provides the following commands:

  crossrefs FIXME
  path <dir> = adds <dir> to the search path for databases
  stylepath <dir> = adds <dir> to the search path for styles
  tool FIXME
"""

import rubber.biblio
import rubber.module_interface

class Module (rubber.module_interface.Module):
	def __init__ (self, document, context):
		self.dep = rubber.biblio.BibTeXDep (document, document.basename ())

		document.hook_macro ("bibliography", "a", self.dep.hook_bibliography)
		document.hook_macro ("bibliographystyle", "a", self.dep.hook_bibliographystyle)

	def command (self, cmd, args):
		self.dep.bib_command (cmd, args)
