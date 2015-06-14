# This file is part of Rubber and thus covered by the GPL
# (c) Ferdinand Schwenk, 2013
# vim: noet:ts=4
"""
pythontex support for Rubber
"""

from rubber import _, msg

import os.path
import shutil
import subprocess


class PythonTeX (object):
	def __init__ (self, doc, context):
		self.doc = doc

	def pre_compile (self):
		if not os.path.exists(self.doc.target + '.pytxcode'):
			msg.info(_("Need compilation!"), pkg="pythontex")
			self.force_compilation()
		msg.info(_("running pythontex..."), pkg="pythontex")
		self.run_pythontex()
		self.doc.watch_file(self.doc.target + ".pytxcode")
		return True

	def clean (self):
		self.doc.remove_suffixes([".pytxcode"])
		pythontex_files = 'pythontex-files-' + os.path.basename(self.doc.target)
		if os.path.exists(pythontex_files):
			msg.log(_("removing tree %s") % pythontex_files)
			shutil.rmtree(pythontex_files)

	def run_pythontex(self):
		call = ['pythontex', self.doc.target + '.tex', ]
		msg.debug(_("pythontex call is '%s'") % ' '.join(call), pkg="pythontex")
		if not self.doc.env.is_in_unsafe_mode_:
			msg.error(_("the document tries to run external programs which could be dangerous.  use rubber --unsafe if the document is trusted."))
			return
		subprocess.call(call)

	def force_compilation(self):
		self.doc.compile()

def setup (doc, context):
	global pytex
	pytex = PythonTeX(doc, context)
def pre_compile ():
	return pytex.pre_compile()
def clean ():
	pytex.clean()

