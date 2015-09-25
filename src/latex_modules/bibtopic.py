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
import rubber.util
from rubber.util import _, msg
from rubber.biblio import Bibliography

def remove (path):
    try:
        os.remove (path)
        msg.log(_("removing {}").format(msg.simplify (path)), pkg="bibtopic")
    except OSError:
        pass

class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        self.btsect_environments = []
        self.current_style = "plain"
        self.doc = document

        document.hook_begin ("btSect", self.on_begin_btsect)

        # Replacing these two default hooks avoids that bibtex.py is
        # loaded automatically as a rubber module (it is loaded as a
        # python module at the beginning of this source).
        document.hook_macro ('bibliography', 'a', self.hook_bibliography)
        document.hook_macro ('bibliographystyle', 'a', self.hook_bibliographystyle)

    def on_begin_btsect (self, loc):
        name = self.doc.basename() + str (len (self.btsect_environments) + 1)
        e = Bibliography (self.doc, name)
        e.set_style (self.current_style)
        self.btsect_environments.append (e)

    def hook_bibliography (self, loc, bibs):
        msg.error(_("incompatible with \\bibliography"), pkg="bibtopic")
        sys.exit (2)

    def hook_bibliographystyle (self, loc, name):
        self.current_style = name

    def pre_compile (self):
        for bib in self.btsect_environments:
            if not bib.pre_compile ():
                return False
        return True

    def clean (self):
        remove ("btaux.aux")
        remove ("btbbl.aux")
        for e in self.btsect_environments:
            e.clean ()
            remove (e.aux)
