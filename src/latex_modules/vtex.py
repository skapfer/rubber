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

    def __init__ (self, document, context):
        document.vars['engine'] = 'VTeX'
        if context['opt'] == 'ps':
            if document.env.final != document and document.products[0][-4:] != '.ps':
                msg.error(_("there is already a post-processor registered"))
                sys.exit(2)
            document.vars['program'] = 'vlatexp'
            document.set_primary_product_suffix (".ps")
        else:
            if document.env.final != document and document.products[0][-4:] != '.pdf':
                msg.error(_("there is already a post-processor registered"))
                sys.exit(2)
            document.vars['program'] = 'vlatex'
            document.set_primary_product_suffix (".pdf")
        document.cmdline = ['-n1', '@latex', '%s']
