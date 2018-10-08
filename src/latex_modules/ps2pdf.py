# vim: et:ts=4
# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2004--2006
"""
PostScript to PDF conversion using GhostScript.
"""

from rubber.depend import Shell
from rubber.util import _
import logging
msg = logging.getLogger (__name__)
import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):
        ps = document.env.final.primary_product ()
        if not ps.endswith ('.ps'):
            raise rubber.GenericError (_("ps2pdf cannot produce PS"))
        pdf = ps[:-2] + 'pdf'
        dep = Shell (('ps2pdf', ps, pdf))
        dep.add_product (pdf)
        dep.add_source (ps)
        document.env.final = dep
