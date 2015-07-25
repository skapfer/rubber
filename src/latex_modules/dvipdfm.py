# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2003--2006
"""
PDF generation through dvipdfm with Rubber.
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

		source = document.env.final.products[0]
		document.env.final = self
		self.add_product (source [:-3] + 'pdf')
		self.add_source (source)
		self.env = document.env
                tool = 'dvipdfm'
		self.cmd = [tool]
		for opt in document.vars ['paper'].split ():
			self.cmd.extend (('-p', opt))
		self.cmd.append (source)
		if source[-4:] != '.dvi':
			msg.error(_("I can't use %s when not producing a DVI")%tool)
			sys.exit(2)

	def do_options (self, *args):
		cmd = self.cmd [:-1]
		cmd.extend (args)
		cmd.append (self.cmd [-1])
		self.cmd = cmd

	def run (self):
		if self.env.execute (self.cmd, kpse=1) != 0:
			msg.error(_("dvipdfm failed on %s") % self.cmd [1])
			return False
		return True
