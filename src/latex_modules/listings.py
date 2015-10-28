# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2003--2006
"""
Dependency analysis and environment parsing for package 'listings' in Rubber.
"""

import rubber.module_interface
class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        self.doc = document
        document.hook_macro ('lstinputlisting', 'oa', self.hook_input)
        document.hook_macro ('lstnewenvironment', 'a', self.hook_newenvironment)
        document.hook_begin ('lstlisting',
                        lambda loc: document.h_begin_verbatim (loc, env='lstlisting'))

    def hook_input (self, loc, opt, file):
        if file.find('\\') < 0 and file.find('#') < 0:
            self.doc.add_source(file)

    def hook_newenvironment (self, loc, name):
        self.doc.hook_begin (name,
                             lambda loc: self.doc.h_begin_verbatim (loc, env=name))
