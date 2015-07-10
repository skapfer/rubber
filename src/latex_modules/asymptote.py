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
import rubber.util

def msg (level, format, *paths):
    translated = rubber.util._ (format)
    substitutions = map (rubber.util.msg.simplify, paths)
    formatted = translated.format (*substitutions)
    method = getattr (rubber.util.msg, level)
    method (formatted, pkg="asy")

def remove (path):
    try:
        os.remove (path)
        msg ("log", "removing {}", path)
    except OSError:
        pass

class Asy_Environment:
    pass

def setup (document, context):
    global doc
    doc = document

    if (document.vars ['engine'] == 'pdfTeX'
        and document.products [0] [-4:] == '.pdf'):
        format = ".pdf"
    elif (document.vars ['engine'] == 'VTeX'):
        msg ("error", "asymptote module does not know how to handle VTeX")
    else:
        format = ".eps"

    inline = context ['opt'] != None \
             and rubber.util.parse_keyval (context ['opt']).has_key ('inline')

    if inline:
        product_suffixes = ("_0" + format, ".pre", ".tex")
    else:
        product_suffixes = (format, )

    def on_begin_asy (loc):
        # Do not parse between \begin{asy} and \end{asy} as LaTeX.
        document.h_begin_verbatim (loc, env="asy")

        e = Asy_Environment ()
        asy_environments.append (e)
        prefix = doc.target + "-" + str (len (asy_environments))
        e.source = prefix + ".asy"
        e.checksum = rubber.util.md5_file (e.source)
        e.products = (prefix + suffix for suffix in product_suffixes)
    doc.hook_begin ("asy", on_begin_asy)

asy_environments = []

def post_compile ():
    prog = ["asy"]
    for e in asy_environments:
        new = rubber.util.md5_file (e.source)
        if new == None:
            msg ("error", "LaTeX should create {}", e.source)
            return False
        if new != e.checksum:
            msg ("log", "{} has changed", e.source)
            e.checksum = new
            prog.append (e.source)
        else:
            for p in e.products:
                if not os.path.exists (p):
                    msg ("log", "output file {} doesn't exist", p)
                    prog.append (e.source)
                    break

    if 1 == len (prog):
        return True

    doc.must_compile = True

    aux = doc.target + ".aux"
    bak = aux + ".tmp"
    msg ("log", "saving {} to {}", aux, bak)
    os.rename (aux, bak)
    ret = doc.env.execute (prog)
    msg ("log", "restoring {} from {}", aux, bak)
    os.rename (bak, aux)
    return ret == 0

def clean ():
    remove (doc.target + ".aux.tmp")
    remove (doc.target + ".pre")
    for e in asy_environments:
        remove (e.source)
        e.checksum = None
        for p in e.products:
            remove (p)
