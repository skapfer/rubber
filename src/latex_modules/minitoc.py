# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
"""
Support for the minitoc package.

This package allows for the insertion of partial tables of contents at the
level of chapters, parts and sections. This nice feature has the drawback of
producing a lot of auxiliary files, and this module handles the cleaning of
these.

It relies on the listfiles option, wich is active by default. Listing
the produced files is quite complex (see shortext option for example).
"""

import os.path

from rubber import _, msg

def setup (document, context):
    global maf
    maf = document.basename (with_suffix = ".maf")

def clean ():
    if os.path.exists (maf):
        with open (maf, "r") as list:
            for name in list:
                name = name.rstrip ()
                msg.log (_ ("removing %s") % name, pkg='minitoc')
                os.remove (name)
        msg.log (_ ("removing %s") % maf, pkg='minitoc')
        os.remove (maf)
