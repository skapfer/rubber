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

The inline option may be passed with \usepackage[inline]{asymptote} or
\begin[inline]{asy}, and asks 'asy' to produce and insert TeX output
instead of .eps/.pdf. As rubber currently fails to report environment
options, only the former is recognized.

Asymptote insists on replacing the main .aux file with an empty one,
so we backup its content before running the external tool.
"""

import os.path
import rubber.depend
import rubber.util

def msg (level, format, *paths):
    translated = rubber.util._ (format)
    substitutions = map (rubber.util.msg.simplify, paths)
    formatted = translated.format (*substitutions)
    method = getattr (rubber.util.msg, level)
    method (formatted, pkg="asymptote")

# Returns None if inline is unset, else a boolean.
def inline_option (option_string):
    options = rubber.util.parse_keyval (option_string)
    try:
        value = options ['inline']
    except KeyError:            # No inline option.
        return None
    return value == None or value == "true"

def setup (document, context):
    global asy_environments
    asy_environments = 0

    document.add_product (document.basename (with_suffix = ".pre"))
    Shell_Restoring_Aux.initialize (document)

    if (document.vars ['engine'] == 'pdfTeX'
        and document.products [0] [-4:] == '.pdf'):
        format = ".pdf"
    elif (document.vars ['engine'] == 'VTeX'):
        msg ("error", "asymptote module does not know how to handle VTeX")
    else:
        format = ".eps"

    global_inline = inline_option (context ['opt'])

    def on_begin_asy (loc):
        environment_options = None
        # For the moment, I hardly see how to parse optional
        # environment arguments.

        # Do not parse between \begin{asy} and \end{asy} as LaTeX.
        document.h_begin_verbatim (loc, env="asy")

        global asy_environments
        asy_environments += 1
        prefix = document.basename (with_suffix = "-" + str (asy_environments))
        source = prefix + ".asy"

        inline = inline_option (environment_options)
        if inline == None:
            inline = global_inline
            if inline == None:
                inline = False
        if inline:
            products = [prefix + suffix for suffix in ("_0" + format, ".pre", ".tex")]
        else:
            products = [prefix + format]

        document.add_product (source)
        node = Shell_Restoring_Aux (set      = document.set,
                                    command  = ["asy", source],
                                    products = products,
                                    sources  = [])
        node.add_source (source, track_contents=True)
        document.add_source (products [0])

    document.hook_begin ("asy", on_begin_asy)


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
            msg ("info", "{} not yet generated", source)
            return True
        os.rename (self.aux, self.bak)
        msg ("log", "saving {} to {}", self.aux, self.bak)
        ret = rubber.depend.Shell.run (self)
        msg ("log", "restoring {} to {}", self.aux, self.bak)
        os.rename (self.bak, self.aux)
        return ret
