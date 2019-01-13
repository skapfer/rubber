# bibtopic.py, part of Rubber building system for LaTeX documents..

# Copyright (C) 2015-2015 Nicolas Boulenguez <nicolas.boulenguez@free.fr>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Support for the 'bibtopic' LaTeX package.

Each 'btSect' environment generates separate .aux and .bbl files.
The .aux must then be processed by 'bibtex' to produce a more
interesting .bbl, and also a .bbl log.
"""

import os.path
from rubber.util import _
import logging
msg = logging.getLogger (__name__)
import rubber.biblio
import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):
        self.btsect_environments = 0
        self.current_style = "plain"
        self.doc = document

        document.hook_begin ("btSect", self.on_begin_btsect)

        # Replacing these two default hooks avoids that bibtex.py is
        # loaded automatically as a rubber module (it is loaded as a
        # python module at the beginning of this source).
        document.hook_macro ('bibliography', 'a', self.hook_bibliography)
        document.hook_macro ('bibliographystyle', 'a', self.hook_bibliographystyle)

        document.add_product ('btaux.aux')
        document.add_product ('btbbl.aux')

    def on_begin_btsect (self, loc):
        self.btsect_environments += 1
        name = self.doc.basename() + str (self.btsect_environments)
        self.doc.add_product (name + ".aux")
        e = rubber.biblio.BibTeXDep (self.doc, name)
        e.set_style (self.current_style)

    def hook_bibliography (self, loc, bibs):
        raise rubber.GenericError (_("\\usepackage{bibtopic} and \\bibliography are incompatible"))

    def hook_bibliographystyle (self, loc, name):
        self.current_style = name
