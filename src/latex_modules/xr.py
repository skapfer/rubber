# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
"""
Dependency analysis for the xr package.

The xr package allows one to put references in one document to other
(external) LaTeX documents. It works by reading the external document's .aux
file, so this support package registers these files as dependencies.
"""

from rubber.util import _
import logging
msg = logging.getLogger (__name__)
import rubber.module_interface

class Module (rubber.module_interface.Module):
    def __init__ (self, document, opt):
        self.doc=document
        document.hook_macro('externaldocument', 'oa', self.hook_externaldocument)

    def hook_externaldocument (self, loc, opt, name):
        aux = self.doc.env.find_file(name + '.aux')
        if aux:
            self.doc.add_source(aux)
            msg.debug( _(
                "dependency %s added for external references") % aux)
        else:
            msg.debug(_(
                "file %s.aux is required by xr package but not found") % name)
