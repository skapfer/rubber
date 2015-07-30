# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2003--2006
"""
PDF generation through dvipdfm with Rubber.
"""

import sys

from rubber import _, msg
import rubber.depend

# FIXME: this class may probably be simplified a lot if inheriting
# from rubber.depend.Shell instead of rubber.depend.Node.

class Dep (rubber.depend.Node):
	def __init__ (self, doc, source):
		super (Dep, self).__init__ (doc.env.depends)
		self.add_product (source [:-3] + 'pdf')
		self.add_source (source)
		self.env = doc.env
                tool = 'dvipdfm'
		self.cmd = [tool]
		for opt in doc.vars ['paper'].split ():
			self.cmd.extend (('-p', opt))
		self.cmd.append (source)
		if source[-4:] != '.dvi':
			msg.error(_("I can't use %s when not producing a DVI")%tool)
			sys.exit(2)

	def do_options (self, args):
		cmd = self.cmd [:-1]
		cmd.extend (args)
		cmd.append (self.cmd [-1])
		self.cmd = cmd

	def run (self):
		if self.env.execute (self.cmd, kpse=1) != 0:
			msg.error(_("dvipdfm failed on %s") % self.cmd [1])
			return False
		return True

def setup (doc, context):
	dvi = doc.env.final.products[0]
	global dep
	dep = Dep(doc, dvi)
	doc.env.final = dep

def do_options (*args):
	dep.do_options (args)
