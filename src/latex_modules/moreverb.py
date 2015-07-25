# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2003--2006
"""
Dependency analysis and environment parsing for package 'moreverb' in Rubber.
"""

import rubber.module_interface
class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        self.doc = document
        document.hook_macro('verbatimtabinput', 'oa', self.hook_verbatimtabinput)
        document.hook_macro('listinginput', 'oaa', self.hook_listinginput)
        for env in [
                'verbatimtab', 'verbatimwrite', 'boxedverbatim', 'comment',
                'listing', 'listing*', 'listingcont', 'listingcont*']:
            document.hook_begin(env, lambda loc: document.h_begin_verbatim(loc, env=env))

    def hook_verbatimtabinput (self, loc, tabwidth, file):
        if file.find('\\') < 0 and file.find('#') < 0:
            self.doc.add_source(file)

    def hook_listinginput (self, loc, interval, start, file):
        if file.find('\\') < 0 and file.find('#') < 0:
            self.doc.add_source(file)
