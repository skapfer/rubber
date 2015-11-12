# This file is part of Rubber and thus covered by the GPL
# Sebastian Kapfer <sebastian.kapfer@fau.de>
# vim: noet:ts=4
"""
Literate programming support for Rubber.

Nodes to make the main TeX file.
"""

import rubber.depend

class LHSDep (rubber.depend.Pipe):
	def __init__ (self, set, target, source):
		super (LHSDep, self).__init__(set, ['lhs2tex', '--poly', source], target)
		self.add_source (source)

class CWebDep (rubber.depend.Shell):
	def __init__ (self, set, target, source):
		assert target[-4:] == '.tex'
		base = target[:-4]
		super (CWebDep, self).__init__(set, ["cweave", source, target])
		self.add_product (target)
		self.add_product (base + ".idx")
		self.add_product (base + ".scn")
		self.add_source (source)

class KnitrDep (rubber.depend.Shell):
	def __init__ (self, set, target, source):
		super (KnitrDep, self).__init__(set, ['R', '-e', 'library(knitr); knit("%s")' % source])
		self.add_source (source)
		self.add_product (target)

literate_preprocessors = { ".lhs": LHSDep, ".w": CWebDep, ".Rtex": KnitrDep }
