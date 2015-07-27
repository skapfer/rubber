# This file is part of Rubber and thus covered by the GPL
# Sebastian Kapfer <sebastian.kapfer@fau.de> 2015.
# based on code by Sebastian Reichel and others.
# vim: noet:ts=4
"""
Bibliographies (Biber and BibTeX).
"""

from rubber.util import _, msg
import rubber.util
from rubber.depend import Shell
import os, os.path

def find_resource (name, suffix="", environ_path=None):
	"""
	find the indicated file, mimicking what latex would do:
	tries adding a suffix such as ".bib",
	or looking in paths (set environ_path to things like "BIBINPUTS")
	if unsuccessful, returns None.
	"""
	from_environ = []
	if environ_path is not None:
		environ_path = os.getenv (environ_path)
		if environ_path is not None:
			from_environ = environ_path.split (":")

	for path in [ "." ] + from_environ:
		fullname = os.path.join (path, name)
		if os.path.exists (fullname):
			return fullname
		elif suffix != "" and os.path.exists (fullname + suffix):
			return fullname + suffix

	msg.warn (_("cannot find %s") % name, pkg="find_resource")
	return None

class BibTool (Shell):
	"""
	Shared code between bibtex and biber support.
	"""
	def __init__ (self, set, doc, tool):
		self.doc = doc
		assert tool in [ "biber", "bibtex" ]
		self.tool = tool
		Shell.__init__ (self, set, command=[ None, doc.basename () ])
		for suf in [ ".bbl", ".blg", ".run.xml" ]:
			self.add_product (doc.basename (with_suffix=suf))

	def add_bib_resource (self, doc, opt, name):
		"""new bib resource discovered"""
		msg.log (_("bibliography resource discovered: %s" % name), pkg="biblio")
		options = rubber.util.parse_keyval (opt)

		# If the file name looks like it contains a control sequence
		# or a macro argument, forget about this resource.
		if name.find('\\') > 0 or name.find('#') > 0:
			return

		# skip Biber remote resources
		if "location" in options and options["location"] == "remote":
			return

		filename = find_resource (name, suffix=".bib", environ_path="BIBINPUTS")
		if filename is None:
			msg.error (_ ("cannot find bibliography resource %s") % name, pkg="biblio")
		else:
			self.add_source (filename)

	def add_bibliography (self, doc, names):
		for bib in names.split (","):
			self.add_bib_resource (doc, None, bib.strip ())

	def run (self):
		# check if the input file exists. if not, refuse to run.
		if not os.path.exists (self.sources[0]):
			msg.info (_("Input file for %s does not yet exist.") % self.tool, pkg="biblio")
			return True
		# command might have been updated in the mean time, so get it now
		# FIXME make tool configurable
		self.command[0] = self.tool
		if Shell.run (self):
			return True
		msg.warn (_("There were errors running %s.") % self.tool, pkg="biblio")
		return False

class BibTeX (BibTool):
	"""Node: make .bbl from .aux using BibTeX"""
	def __init__ (self, set, doc):
		BibTool.__init__ (self, set, doc, "bibtex")
		doc.hook_macro ("bibliography", "a", self.add_bibliography)
		self.add_source (doc.basename (with_suffix=".aux"), track_contents=True)
		doc.add_product (doc.basename (with_suffix="-blx.bib"))

	def run (self):
		# strip abspath, to allow BibTeX to write the bbl.
		self.command[1] = os.path.basename (self.sources[0])
		return BibTool.run (self)

class Biber (BibTool):
	"""Node: make .bbl from .bcf using Biber"""
	def __init__ (self, set, doc):
		BibTool.__init__ (self, set, doc, "biber")
		for macro in ("addbibresource", "addglobalbib", "addsectionbib"):
			doc.hook_macro (macro, "oa", self.add_bib_resource)
		doc.hook_macro ("bibliography", "a", self.add_bibliography)
		self.add_source (doc.basename (with_suffix=".bcf"), track_contents=True)
		doc.add_product (doc.basename (with_suffix=".bcf"))

def setup (doc, what="biber"):
	(Biber if what=="biber" else BibTeX) (doc.set, doc)
	doc.add_source (doc.basename (with_suffix=".bbl"), track_contents=True)
