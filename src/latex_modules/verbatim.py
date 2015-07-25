# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2003--2006
"""
Dependency analysis and environment parsing for package 'verbatim' in Rubber.
"""

import rubber.module_interface
class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        self.doc = document
        document.hook_macro('verbatiminput', 'a', self.hook_input)
        document.hook_begin('comment', self.hook_begin_comment)

    def hook_begin_comment (self, loc):
        self.doc.h_begin_verbatim(loc, env='comment')

    def hook_input (self, loc, file):
        if file.find('\\') < 0 and file.find('#') < 0:
            self.doc.add_source(file)
