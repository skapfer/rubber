# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# (c) Sebastian Kapfer 2015
# vim:et:ts=4
"""
PostScript generation through dvips with Rubber.

This module has specific support for Omega: when the name of the main compiler
is "Omega" (instead of "TeX" for instance), then "odvips" is used instead of
"dvips".
"""

import sys

from rubber import _, msg
import rubber.depend
import rubber.module_interface

# FIXME: this class may probably be simplified a lot if inheriting
# from rubber.depend.Shell instead of rubber.depend.Node.

class Module (rubber.depend.Node, rubber.module_interface.Module):

    def __init__ (self, document, context):
        super (Module, self).__init__ (document.env.depends)

        self.doc = document
        self.source = self.doc.env.final.products[0]
        self.doc.env.final = self

        self.add_product (self.source[:-3] + 'ps')
        self.add_source (self.source)
        self.extra_args = []

    def do_options (self, *args):
        self.extra_args.extend (args)

    def run (self):
        # build command line
        if self.doc.vars['engine'] == 'Omega':
            tool = 'odvips'
        else:
            tool = 'dvips'
        cmd = [ tool ]
        for opt in self.doc.vars['paper'].split ():
            cmd.extend ([ '-t', opt ])
        cmd.extend (self.extra_args)
        cmd.append (self.source)
        if not self.source.endswith ('.dvi'):
            msg.error (_('I can\'t use %s when not producing a DVI') % tool)
            sys.exit (2)

        # run
        if self.doc.env.execute (cmd, kpse=1) != 0:
            msg.error (_('dvips failed on %s') % self.source)
            return False
        return True
