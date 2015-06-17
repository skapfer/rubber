# This file is part of Rubber and thus covered by the GPL
# Sebastian Kapfer <sebastian.kapfer@fau.de>
# vim: noet:ts=4
"""
Literate programming support for Rubber.

Nodes to make the main TeX file.
"""

from rubber.depend import Pipe, Shell

class LHSDep (Pipe):
	def __init__ (self, set, target, source):
		Pipe.__init__(self, set,
			['lhs2tex', '--poly', source],
			[target],
			[source])

class CWebDep (Shell):
	def __init__ (self, set, target, source):
		assert target[-4:] == '.tex'
		base = target[:-4]
		Shell.__init__(self, set,
			["cweave", source, target],
			[target, base + ".idx", base + ".scn"],
			[source])

class KnitrDep (Shell):
	def __init__ (self, set, target, source):
		Pipe.__init__(self, set,
			['R', '-e', 'library(knitr); knit("%s")' % source],
			[target],
			[source])

literate_preprocessors = { ".lhs": LHSDep, ".w": CWebDep, ".Rtex": KnitrDep }
