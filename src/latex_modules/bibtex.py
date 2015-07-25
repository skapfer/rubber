# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# vim: noet:ts=4
"""
BibTeX support for Rubber

This module is a special one: it is triggered by the macros \\bibliography and
\\bibliographystyle and not as a package, so the main system knows about it.
The module provides the following commands:

  path <dir> = adds <dir> to the search path for databases
  stylepath <dir> = adds <dir> to the search path for styles
"""

import rubber.biblio
import rubber.module_interface

class Module (rubber.biblio.Bibliography, rubber.module_interface.Module):
    def __init__ (self, document, context):
        super (Module, self).__init__ (document)
        document.hook_macro('bibliography', 'a', self.hook_bibliography)
        document.hook_macro('bibliographystyle', 'a', self.hook_bibliographystyle)
