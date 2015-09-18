# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2003--2006
"""
Epsfig support for Rubber.

The package 'epsfig' is a somewhat deprecated interface to the graphics module
that simply provides a macro \\psfig with a keyval list argument to include
an EPS figure file.
"""

from rubber.util import parse_keyval
import rubber.module_interface

class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        document.do_module('graphics')
        _, self.hook_includegraphics = document.hooks['includegraphics']
        # We proceed as if \epsfbox and \includegraphics were equivalent.
        document.hook_macro('epsfbox', 'oa', self.hook_epsfbox)
        document.hook_macro('epsffile', 'oa', self.hook_epsfbox)
        document.hook_macro('epsfig', 'a', self.hook_epsfig)
        document.hook_macro('psfig', 'a', self.hook_epsfig)

    def hook_epsfbox (self, loc, optional, argument):
        self.hook_includegraphics(loc, False, optional, argument)

    def hook_epsfig (self, loc, argument):
        # We just translate this into an equivalent call to \includegraphics.
        options = parse_keyval(argument)
        if 'file' not in options:
            return
        self.hook_includegraphics(loc, False, argument, options['file'])
