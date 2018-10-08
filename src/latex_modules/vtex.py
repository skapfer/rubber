# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# vim: noet:ts=4
"""
VTeX support for Rubber.

This module specifies that the VTeX/Free compiler should be used. This
includes using "vlatex" of "vlatexp" instead of "latex" and knowing that this
produces a PDF or PostScript file directly. The PDF version is used by
default, switching to PS is possible by using the module option "ps".
"""

import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):
        document.engine = 'VTeX'
        if opt == 'ps':
            document.program = 'vlatexp'
            document.register_post_processor (old_suffix='.ps', new_suffix='.ps')
        else:
            document.program = 'vlatex'
            document.register_post_processor (old_suffix='.pdf', new_suffix='.pdf')
        document.cmdline = ['-n1', '@latex', '%s']
