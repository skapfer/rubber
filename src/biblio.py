# This file is part of Rubber and thus covered by the GPL
# Sebastian Kapfer <sebastian.kapfer@fau.de> 2015.
# based on code by Sebastian Reichel and others.
# vim: noet:ts=4
"""
Bibliographies (Biber and BibTeX).
"""

from rubber.util import _, msg
import rubber.util
import rubber.depend
import os, os.path
import re
import string

def find_resource (name, suffix="", environ_path=None):
	"""
	find the indicated file, mimicking what latex would do:
	tries adding a suffix such as ".bib",
	or looking in paths (set environ_path to things like "BIBINPUTS")
	if unsuccessful, returns None.
	"""
	name = name.strip ()
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
	return None

class BibLatexTool (rubber.depend.Shell):
	"""
	Shared code between bibtex and biber support.
	"""
	def __init__ (self, set, doc, tool):
		self.doc = doc
		assert tool in [ "biber", "bibtex" ]
		self.tool = tool
		super (BibLatexTool, self).__init__ (set, command=[ None, doc.basename () ])
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
		if super (BibLatexTool, self).run ():
			return True
		msg.warn (_("There were errors running %s.") % self.tool, pkg="biblio")
		return False

class BibTeX (BibLatexTool):
	"""
	Node: make .bbl from .aux using BibTeX (or BibTeX8, or BibTeXu) for use
	with BibLaTeX
	"""
	def __init__ (self, set, doc, tool):
		super (BibTeX, self).__init__ (set, doc, tool)
		doc.hook_macro ("bibliography", "a", self.add_bibliography)
		self.add_source (doc.basename (with_suffix=".aux"), track_contents=True)
		doc.add_product (doc.basename (with_suffix="-blx.bib"))
		doc.add_source (doc.basename (with_suffix=".bbl"), track_contents=True)

	def run (self):
		# strip abspath, to allow BibTeX to write the bbl.
		self.command[1] = os.path.basename (self.sources[0])
		return super (BibTeX, self).run ()

class Biber (BibLatexTool):
	"""Node: make .bbl from .bcf using Biber"""
	def __init__ (self, set, doc):
		super (Biber, self).__init__ (set, doc, "biber")
		for macro in ("addbibresource", "addglobalbib", "addsectionbib"):
			doc.hook_macro (macro, "oa", self.add_bib_resource)
		doc.hook_macro ("bibliography", "a", self.add_bibliography)
		self.add_source (doc.basename (with_suffix=".bcf"), track_contents=True)
		doc.add_product (doc.basename (with_suffix=".bcf"))
		doc.add_source (doc.basename (with_suffix=".bbl"), track_contents=True)


# The regular expression that identifies errors in BibTeX log files is heavily
# heuristic. The remark is that all error messages end with a text of the form
# "---line xxx of file yyy" or "---while reading file zzz". The actual error
# is either the text before the dashes or the text on the previous line.

re_error = re.compile(
	"---(line (?P<line>[0-9]+) of|while reading) file (?P<file>.*)")

class Bibliography (rubber.depend.Node):
	"""
	This class represents a single bibliography for a document.
	"""
	def __init__ (self, document, aux_basename=None):
		"""
		Initialise the bibiliography for the given document. The base name is
		that of the aux file from which citations are taken.
		"""
		super (Bibliography, self).__init__ (document.set)
		self.doc = document
		jobname = os.path.basename (document.target)
		if aux_basename == None:
			aux_basename = jobname
		self.log = jobname + ".log"
		self.aux = aux_basename + ".aux"
		self.bbl = aux_basename + ".bbl"
		self.blg = aux_basename + ".blg"
		self.add_product (self.bbl)
		self.add_product (self.blg)
		self.add_source (self.aux, track_contents=True)

		cwd = document.vars["cwd"]
		self.bib_path = [cwd, document.vars["path"]]
		self.bst_path = [cwd]

		self.bst_file = None
		self.set_style ("plain")
		self.db = {}
		self.crossrefs = None

	#
	# The following method are used to specify the various datafiles that
	# BibTeX uses.
	#

	def do_crossrefs (self, number):
		self.crossrefs = number

	def do_path (self, path):
		self.bib_path.append(self.doc.abspath(path))

	def do_stylepath (self, path):
		self.bst_path.append(self.doc.abspath(path))

	def do_sorted (self, mode):
		# ignored option
		pass

	def hook_bibliography (self, loc, bibs):
		for name in string.split (bibs, ","):
			filename = find_resource (name, suffix=".bib", environ_path="BIBINPUTS")
			if filename is not None:
				self.db[name] = filename
				self.add_source (filename, track_contents=True)
			else:
				msg.error (_ ("cannot find bibliography resource %s") % name, pkg="biblio")

	def hook_bibliographystyle (self, loc, name):
		"""
		Define the bibliography style used. This method is called when
		\\bibliographystyle is found. If the style file is found in the
		current directory, it is considered a dependency.
		"""
		self.set_style (name)

	def set_style (self, name):
		if self.bst_file is not None:
			self.remove_source (self.bst_file)
			self.bst_file = None

		filename = find_resource (name, suffix=".bst", environ_path="BSTINPUTS")
		if filename is not None:
			self.bst_file = filename
			self.add_source (filename, track_contents=True)
		elif name not in [ "plain", "alpha" ]:
			# do not complain about default styles coming with bibtex
			msg.warn (_ ("cannot find bibliography style %s") % name, pkg="biblio")

	def pre_compile (self):
		return True

	def run (self):
		"""
		This method actually runs BibTeX with the appropriate environment
		variables set.
		"""
		msg.progress(_("running BibTeX on %s") % self.aux)
		doc = {}
		if len(self.bib_path) != 1:
			doc["BIBINPUTS"] = string.join(self.bib_path +
				[os.getenv("BIBINPUTS", "")], ":")
		if len(self.bst_path) != 1:
			doc["BSTINPUTS"] = string.join(self.bst_path +
				[os.getenv("BSTINPUTS", "")], ":")
		if self.crossrefs is None:
			cmd = ["bibtex"]
		else:
			cmd = ["bibtex", "-min-crossrefs=" + self.crossrefs]
		if self.doc.env.execute (['bibtex', self.aux], doc):
			msg.info(_("There were errors making the bibliography."))
			return False
		return True

	#
	# The following method extract information from BibTeX log files.
	#

	def get_errors (self):
		"""
		Read the log file, identify error messages and report them.
		"""
		if not os.path.exists (self.blg):
			return
		with open (self.blg) as log:
			last_line = ""
			for line in log:
				m = re_error.search(line)
				if m:
					# TODO: it would be possible to report the offending code.
					if m.start() == 0:
						text = string.strip(last_line)
					else:
						text = string.strip(line[:m.start()])
					line = m.group("line")
					if line: line = int(line)
					d =	{
						"pkg": "bibtex",
						"kind": "error",
						"text": text
						}
					d.update( m.groupdict() )

					# BibTeX does not report the path of the database in its log.

					file = d["file"]
					if file[-4:] == ".bib":
						file = file[:-4]
					if self.db.has_key(file):
						d["file"] = self.db[file]
					elif self.db.has_key(file + ".bib"):
						d["file"] = self.db[file + ".bib"]
					yield d
				last_line = line
