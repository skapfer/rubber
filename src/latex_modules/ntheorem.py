# ntheorem.py, part of Rubber building system for LaTeX documents..

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
This module supports the 'ntheorem' LaTeX package, which a .thm list
of theorems. Next LaTeX runs will read it and use the .aux file in a
more usual way.
"""

import os.path
import rubber.util

def msg (level, format):
    translated = rubber.util._ (format)
    substitutions = rubber.util.msg.simplify (thm)
    formatted = translated.format (substitutions)
    method = getattr (rubber.util.msg, level)
    method (formatted, pkg="ntheorem")

def setup (doc, context):
    global thm
    thm = doc.basename (with_suffix=".thm")
    doc.add_product (thm)
    doc.watch_file (thm)

def post_compile ():
    if not os.path.exists (thm):
        msg ("error", "LaTeX should have created {}")
        return False
    return True
