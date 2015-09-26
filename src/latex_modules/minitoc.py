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
from rubber.util import verbose_remove
import rubber.module_interface

class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        self.maf = document.basename (with_suffix = ".maf")

    def clean (self):
        if os.path.exists (self.maf):
            with open (self.maf, "r") as list:
                for name in list:
                    name = name.rstrip ()
                    verbose_remove (name, pkg = "minitoc")
            verbose_remove (self.maf, pkg = "minitoc")
