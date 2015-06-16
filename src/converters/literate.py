# This file is part of Rubber and thus covered by the GPL
# Sebastian Kapfer <sebastian.kapfer@fau.de>
# vim: noet:ts=4
"""
Literate programming support for Rubber.

Nodes to make the main TeX file.
"""

from subprocess import Popen
from rubber.util import _, msg
from rubber.depend import Node, Shell

class LHSDep (Node):
	def __init__ (self, set, target, source):
		Node.__init__(self, set, [target], [source])
		self.source = source
		self.target = target

	def run (self):
		msg.progress(_("pretty-printing %s") % self.source)
		output = open(self.target, 'w')
		process = Popen(['lhs2tex', '--poly', self.source], stdout=output)
		if process.wait() != 0:
			msg.error(_("pretty-printing of %s failed") % self.source)
			return False
		output.close()
		return True

class CWebDep (Shell):
	def __init__ (self, set, target, source):
		assert target[-4:] == '.tex'
		base = target[:-4]
		Shell.__init__(self, set, ["cweave", source, target],
			[target, base + ".idx", base + ".scn"],
			[source])

literate_preprocessors = { ".lhs": LHSDep, ".w": CWebDep }
