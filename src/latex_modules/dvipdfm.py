# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2003--2006
"""
PDF generation through dvipdfm with Rubber.
"""

import sys

from rubber import _, msg
from rubber.depend import Node

# FIXME: this class may probably be simplified a lot if inheriting
# from rubber.depend.Shell instead of rubber.depend.Node.

class Dep (Node):
	def __init__ (self, doc, target, source):
		Node.__init__(self, doc.env.depends)
		self.add_product (target)
		self.add_source (source)
		self.env = doc.env
		self.cmd = ['dvipdfm', source, '-o', target]
		for opt in doc.vars['paper'].split():
			self.cmd.extend (('-p', opt))

	def do_options (self, args):
		self.cmd.extend (args)

	def run (self):
		msg.progress(_("running dvipdfm on %s") % self.cmd [1])
		if self.env.execute (self.cmd, kpse=1):
			msg.error(_("dvipdfm failed on %s") % self.cmd [1])
			return False
		return True

def setup (doc, context):
	dvi = doc.env.final.products[0]
	if dvi[-4:] != '.dvi':
		msg.error(_("I can't use dvipdfm when not producing a DVI"))
		sys.exit(2)
	pdf = dvi[:-3] + 'pdf'
	global dep
	dep = Dep(doc, pdf, dvi)
	doc.env.final = dep

def do_options (*args):
	dep.do_options (args)
