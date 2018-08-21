# This file is covered by the GPL as part of Rubber.
# (c) Emmanuel Beffara, 2002--2006
"""
Extraction of bounding box information from gzipped PostScript figures.
"""

from rubber.util import _, msg
import rubber.depend

import gzip
import re

re_bbox = re.compile("%[%\w]*BoundingBox:")

class Dep (rubber.depend.Node):
	def __init__ (self, set, target, source):
		super (Dep, self).__init__(set)
		self.add_product (target)
		self.add_source (source)
		self.source = source
		self.target = target

	def run (self):
		"""
		This method reads the source file (which is supposed to be a
		gzip-compressed PostScript file) until it finds a line that contains a
		bounding box indication. Then it creates the target file with this
		single line.
		"""
		msg.progress(_("extracting bounding box from %s") % self.source)
		with gzip.open(self.source, mode='rt', encoding='latin_1') as source:
			for line in source:
				if re_bbox.match(line):
					with open(self.target, 'w', encoding='latin_1') as target:
						target.write(line)
					return True
		msg.error(_("no bounding box was found in %s!") % self.source)
		return False

def convert (source, target, context, env):
	set = env.depends
	return Dep(set, target, source)
