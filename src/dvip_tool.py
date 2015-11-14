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

import abc
from rubber import _, msg
import rubber.converters
import rubber.depend
import rubber.module_interface
import rubber.util

# FIXME: this class may probably be simplified a lot if inheriting
# from rubber.depend.Shell instead of rubber.depend.Node.

product_extension = { 'dvips':'ps', 'dvipdfm':'pdf' }
paper_selection_option = { 'dvips':'-t', 'dvipdfm':'-p' }

class Module (rubber.depend.Node, rubber.module_interface.Module):
    # This class may not be instantiated directly, only subclassed.
    __metaclass__ = abc.ABCMeta

    def __init__ (self, document, context, tool):
        super (Module, self).__init__ (document.env.depends)

        self.tool = tool
        assert tool in ('dvipdfm', 'dvips')
        self.doc = document

        assert type (self.doc.env.final) is rubber.converters.latex.LaTeXDep
        self.source = self.doc.env.final.products[0]
        if not self.source.endswith ('.dvi'):
            msg.error (_('I can\'t use %s when not producing a DVI') % tool)
            rubber.util.abort_generic_error ()
        self.doc.env.final = self
        self.add_product (self.source [:-3] + product_extension [tool])
        self.add_source (self.source)
        self.extra_args = []

    def do_options (self, *args):
        self.extra_args.extend (args)

    def run (self):
        # build command line
        tool = self.tool
        if tool == 'dvips' and self.doc.vars ['engine'] == 'Omega':
            tool = 'odvips'
        cmd = [ tool ]
        for opt in self.doc.vars['paper'].split ():
            cmd.extend ((paper_selection_option [self.tool], opt))
        cmd.extend (self.extra_args)
        cmd.append (self.source)

        # run
        if self.doc.env.execute (cmd, kpse=1) != 0:
            msg.error (_('%s failed on %s') % (tool, self.source))
            return False
        return True
