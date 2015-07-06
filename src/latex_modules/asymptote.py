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
"""

import itertools
import os.path
import rubber.util

def setup (document, context):
    basename = os.path.basename (document.target)

    count = itertools.count (start = 1)

    format = document.products [0] [-4:]
    assert format in (".dvi", ".pdf")
    if format == ".dvi":
        format = ".eps"

    inline = context ['opt'] != None \
             and rubber.util.parse_keyval (context ['opt']).has_key ('inline')

    if inline:
        product_suffixes = ("_0" + format, ".pre", ".tex")
    else:
        product_suffixes = (format, )

    document.do_clean (basename + ".pre")

    def on_begin_asy (loc):
        # Do not parse between \begin{asy} and \end{asy} as LaTeX.
        document.h_begin_verbatim (loc, env="asy")

        prefix = basename + "-" + str (count.next ())
        source = prefix + ".asy"
        document.do_watch (source)
        document.do_onchange (source, "asy " + source)
        document.do_clean (source)
        for s in product_suffixes:
            document.do_clean (prefix + s)
    document.hook_begin ("asy", on_begin_asy)
