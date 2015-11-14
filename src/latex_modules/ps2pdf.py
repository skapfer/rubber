# vim: et:ts=4
# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2004--2006
"""
PostScript to PDF conversion using GhostScript.
"""

from rubber.depend import Shell
from rubber.util import _, msg
import rubber.module_interface
import rubber.util

class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        env = document.env
        if env.final.products[0][-3:] != '.ps':
             msg.error(_("I can't use ps2pdf when not producing a PS"))
             rubber.util.abort_generic_error ()
        ps = env.final.products[0]
        pdf = ps[:-2] + 'pdf'
        cmd = ['ps2pdf']
        for opt in document.vars['paper'].split():
            cmd.append('-sPAPERSIZE=' + opt)
        cmd.extend([ps, pdf])
        dep = Shell (env.depends, cmd)
        dep.add_product (pdf)
        dep.add_source (ps)
        env.final = dep
