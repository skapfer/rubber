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
import subprocess

class BibToolDep (rubber.depend.Node):
	def __init__ (self, set):
		super (BibToolDep, self).__init__ (set)
		self.tool = "bibtex"
		self.environ = os.environ.copy ()
		self.bib_paths = rubber.util.explode_path ("BIBINPUTS")
		self.bst_paths = rubber.util.explode_path ("BSTINPUTS")
		self.devnull = rubber.util.devnull ()

	def do_path (self, path):
		self.bib_paths.insert (0, path)

	def run (self):
		# check if the input file exists. if not, refuse to run.
		if not os.path.exists (self.sources[0]):
			msg.info (_("input file for %s does not yet exist, deferring")
				% self.tool, pkg="biblio")
			return True

		# command might have been updated in the mean time, so get it now
		self.environ["BIBINPUTS"] = ":".join (self.bib_paths)
		self.environ["BSTINPUTS"] = ":".join (self.bst_paths)
		command = self.build_command ()

		msg.progress (_("running: %s") % " ".join (command))
		process = subprocess.Popen (command, stdin = self.devnull,
			stdout = self.devnull, env = self.environ)
		if process.wait() != 0:
			msg.error (_("There were errors running %s.") % self.tool, pkg="biblio")
			return False
		return True


# The regular expression that identifies errors in BibTeX log files is heavily
# heuristic. The remark is that all error messages end with a text of the form
# "---line xxx of file yyy" or "---while reading file zzz". The actual error
# is either the text before the dashes or the text on the previous line.

re_error = re.compile(
	"---(line (?P<line>[0-9]+) of|while reading) file (?P<file>.*)")

class Bibliography (BibToolDep):
	"""
	This class represents a single bibliography for a document.
	"""
	def __init__ (self, document, aux_basename=None):
		"""
		Initialise the bibiliography for the given document. The base name is
		that of the aux file from which citations are taken.
		"""
		super (Bibliography, self).__init__ (document.set)

		if aux_basename == None:
			aux_basename = document.basename()
		self.log = document.basename(with_suffix=".log")
		self.aux = aux_basename + ".aux"
		self.bbl = aux_basename + ".bbl"
		self.blg = aux_basename + ".blg"
		self.add_product (self.bbl)
		self.add_product (self.blg)
		self.add_source (self.aux, track_contents=True)
		document.add_source (self.bbl, track_contents=True)

		self.bst_file = None
		self.set_style ("plain")
		self.db = {}
		self.crossrefs = None

	def build_command (self):
		ret = [ self.tool ]
		if self.crossrefs is not None:
			ret += [ "-min-crossrefs=" + self.crossrefs ]
		return ret + [ self.aux ]

	#
	# The following method are used to specify the various datafiles that
	# BibTeX uses.
	#

	def do_crossrefs (self, number):
		self.crossrefs = number

	def do_stylepath (self, path):
		self.bst_paths.insert (0, path)

	def do_sorted (self, mode):
		# ignored option
		pass

	def do_tool (self, tool):
		# FIXME document this
		self.tool = tool

	def hook_bibliography (self, loc, bibs):
		for name in string.split (bibs, ","):
			filename = rubber.util.find_resource (name, suffix = ".bib", paths = self.bib_paths)
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

		filename = rubber.util.find_resource (name, suffix = ".bst", paths = self.bst_paths)
		if filename is not None:
			self.bst_file = filename
			self.add_source (filename, track_contents=True)
		elif name not in [ "plain", "alpha" ]:
			# do not complain about default styles coming with bibtex
			msg.warn (_ ("cannot find bibliography style %s") % name, pkg="biblio")

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
