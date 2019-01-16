# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# (c) Sebastian Kapfer 2015
# vim:et:ts=4
"""
Abstract class providing a common implementation for
rubber.latex_modules.dvips and rubber.latex_modules.dvipdfm.

PostScript/PDF generation through dvips/odvips/dvipdfm with Rubber.

When the name of the main compiler is "Omega" (instead of "TeX" for
instance), then "odvips" is used instead of "dvips".
"""

from rubber.util import _
import logging
msg = logging.getLogger (__name__)
import rubber.converters
import rubber.depend
import rubber.util

# FIXME: this class may probably be simplified a lot if inheriting
# from rubber.depend.Shell instead of rubber.depend.Node.

product_extension = { 'dvips':'ps', 'dvipdfm':'pdf' }

class Dvip_Tool_Dep_Node (rubber.depend.Node):

    def __init__ (self, document, tool):
        super ().__init__ ()
        self.tool = tool
        assert tool in ('dvipdfm', 'dvips')
        self.doc = document

        assert type (self.doc.env.final) is rubber.converters.latex.LaTeXDep
        self.source = self.doc.env.final.primary_product ()
        if not self.source.endswith ('.dvi'):
            raise rubber.GenericError (_('Tool %s only produces DVI') % tool)
        self.doc.env.final = self
        self.add_product (self.source [:-3] + product_extension [tool])
        self.add_source (self.source)
        self.extra_args = []
        self.delegate_commands_to = self

    def do_options (self, args):
        self.extra_args.extend (args)

    def run (self):
        # build command line
        tool = self.tool
        if tool == 'dvips' and self.doc.engine == 'Omega':
            tool = 'odvips'
        cmd = [ tool ]
        cmd.extend (self.extra_args)
        cmd.append (self.source)

        # run
        if rubber.util.execute (cmd) != 0:
            msg.error (_('%s failed on %s') % (tool, self.source))
            return False
        return True
