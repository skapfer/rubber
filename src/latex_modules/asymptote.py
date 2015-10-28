# asymptote.py, part of Rubber building system for LaTeX documents..

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
This module supports the 'asymptote' LaTeX package.

The content of each 'asy' environment is copied into a separate .asy
file, which must then be processed by the 'asy' external tool to
produce a .eps/.pdf.  If the output already exists, it is inserted,
but a (maybe identical) .asy is created nevertheless.

The inline option may be passed with \\usepackage[inline]{asymptote} or
\begin[inline]{asy}, and asks 'asy' to produce and insert TeX output
instead of .eps/.pdf. As rubber currently fails to report environment
options, only the former is recognized.

Asymptote insists on replacing the main .aux file with an empty one,
so we backup its content before running the external tool.
"""

import os.path
import rubber.depend
import rubber.module_interface
import rubber.util
from rubber.util import _, msg

# Returns None if inline is unset, else a boolean.
def inline_option (option_string, default):
    options = rubber.util.parse_keyval (option_string)
    try:
        value = options ['inline']
    except KeyError:            # No inline option.
        return default
    return value == None or value == "true"

class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        self.asy_environments = 0
        self.doc = document

        document.add_product (document.basename (with_suffix = ".pre"))
        Shell_Restoring_Aux.initialize (document)

        if (document.vars ['engine'] == 'pdfTeX'
            and document.products [0] [-4:] == '.pdf'):
            self.format = ".pdf"
        elif (document.vars ['engine'] == 'VTeX'):
            msg.error(_("does not know how to handle VTeX"), pkg="asymptote")
        else:
            self.format = ".eps"

        self.global_inline = inline_option (context ['opt'], default=False)

        document.hook_begin ("asy", self.on_begin_asy)

    def on_begin_asy (self, loc):
        environment_options = None
        # For the moment, I hardly see how to parse optional
        # environment arguments.

        # Do not parse between \begin{asy} and \end{asy} as LaTeX.
        self.doc.h_begin_verbatim (loc, env="asy")

        self.asy_environments += 1
        prefix = self.doc.basename (with_suffix = "-" + str (self.asy_environments))
        source = prefix + ".asy"

        inline = inline_option (environment_options, default=self.global_inline)

        self.doc.add_product (source)
        node = Shell_Restoring_Aux (self.doc.set, ["asy", source])
        if inline:
            node.add_product (prefix + ".tex")
            node.add_product (prefix + "_0" + self.format)
            node.add_product (prefix + ".pre")
            self.doc.add_source (prefix + ".tex")
        else:
            node.add_product (prefix + self.format)
            self.doc.add_source (prefix + self.format)
        node.add_source (source, track_contents=True)

class Shell_Restoring_Aux (rubber.depend.Shell):
    """This class replaces Shell because of a bug in asymptote. Every run
of /usr/bin/asy flushes the .aux file.

    """
    @classmethod
    def initialize (cls, document):
        cls.aux = document.basename (with_suffix = ".aux")
        cls.bak = document.basename (with_suffix = ".aux.tmp")
        # In case we are interrupted, clean bak.
        document.add_product (cls.bak)

    def run (self):
        source = self.sources [0]
        if not os.path.exists (source):
            msg.info(_("{} not yet generated").format (msg.simplify (source)),
                     pkg="asymptote")
            return True
        os.rename (self.aux, self.bak)
        msg.log (_ ("saving {} to {}").format (msg.simplify (self.aux),
                                               msg.simplify (self.bak)),
                 pkg="asymptote")
        ret = super (Shell_Restoring_Aux, self).run ()
        msg.log (_ ("restoring {} to {}").format (msg.simplify (self.aux),
                                                  msg.simplify (self.bak)),
                pkg="asymptote")
        os.rename (self.bak, self.aux)
        return ret
