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
import rubber.latex_modules.bibtex

def remove (path):
    try:
        os.remove (path)
        msg.log(_("removing {}").format(msg.simplify (path)), pkg="bibtopic")
    except OSError:
        pass

def setup (document, context):
    global basename, btsect_environments, current_style, doc
    basename = os.path.basename (document.target)
    btsect_environments = []
    current_style = "plain"
    doc = document

    document.hook_begin ("btSect", on_begin_btsect)

    # Replacing these two default hooks avoids that bibtex.py is
    # loaded automatically as a rubber module (it is loaded as a
    # python module at the beginning of this source).
    document.hook_macro ('bibliography', 'a', hook_bibliography)
    document.hook_macro ('bibliographystyle', 'a', hook_bibliographystyle)

def on_begin_btsect (loc):
    name = basename + str (len (btsect_environments) + 1)
    e = rubber.latex_modules.bibtex.Bibliography (doc, name)
    e.set_style (current_style)
    btsect_environments.append (e)

def hook_bibliography (loc, bibs):
    msg.error(_("incompatible with \\bibliography"), pkg="bibtopic")
    sys.exit (2)

def hook_bibliographystyle (loc, name):
    global current_style
    current_style = name

def pre_compile ():
    for bib in btsect_environments:
	if not bib.pre_compile ():
	    return False
    return True

def post_compile ():
    for bib in btsect_environments:
	if not bib.post_compile ():
	    return False
    return True

def clean ():
    remove ("btaux.aux")
    remove ("btbbl.aux")
    for e in btsect_environments:
        e.clean ()
        remove (e.aux)
