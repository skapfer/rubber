# vim: noet:ts=4
# This file is covered by the GPL as part of Rubber.
# (c) Emmanuel Beffara, 2002--2006
"""
Metapost support for Rubber.

The module parses input files for dependencies and does some checkings on
Metapost's log files after the process. Is it enough?
"""

import os, os.path
import re, string

from rubber.util import _
from rubber.util import *
import rubber.depend
import rubber.converters.latex

metapost_logfile_limit = 1000000

def check (source, target, context):
	return prog_available('mpost')

re_input = re.compile("input\\s+(?P<file>[^\\s;]+)")
# This is very restrictive, and so is the parsing routine. FIXME?
re_mpext = re.compile("[0-9]+|mpx|log")
re_mpxerr = re.compile("% line (?P<line>[0-9]+) (?P<file>.*)$")

class MPLogCheck (rubber.converters.latex.LogCheck):
	"""
	This class adapats the LogCheck class from the main program to the case of
	MetaPost log files, which are very similar to TeX log files.
	"""
	def __init__ (self, pwd):
		super (MPLogCheck, self).__init__ ()
		self.pwd = pwd

	def read (self, name):
		"""
		The read() method in LogCheck checks that the log is produced by TeX,
		here we check that it is produced by MetaPost.
		"""
		with open (name) as file:
			line = file.readline()
			if not line or line.find("This is MetaPost,") == -1:
				return 1
			self.lines = file.readlines()
		return 0

	def continued (self, line):
		"""
		Messages in Metapost logs are broken at 79 characters per line, except
		in some cases where there are lines of this length that are not
		continued...
		"""
		if len(line) != 79:
			return 0
		return line[-3:] != "..."

	def get_errors (self):
		"""
		Parse the Metapost log file for errors. The file has the same form as
		a TeX log file, so the parser for TeX logs is used. The special case
		is that of TeX errors in Metapost labels, which requires parsing
		another TeX log file.
		"""
		for err in super (MPLogCheck, self).get_errors():
			if (err["kind"] != "error"
				or err["text"] != "Unable to make mpx file."):
				yield err
				continue

			# a TeX error was found: parse mpxerr.log

			log = rubber.converter.latex.LogCheck()
			# FIXME this path has no testcase.
			if not log.readlog (os.path.join(self.pwd, "mpxerr.log"), metapost_logfile_limit):
				yield err
				continue

			# read mpxerr.tex to read line unmbers from it

			with open(os.path.join(self.pwd, "mpxerr.tex")) as tex_file:
				tex = tex_file.readlines()

			# get the name of the mpxNNN.tex source

			for line in log.lines:
				if line[:2] == "**":
					tex_src = os.path.join(".", line[2:].strip())
					break

			for err in log.get_errors():
				if tex_src != err["file"]:
					# the error is not in a Metapost source
					yield err
					continue

				line = int(err["line"])
				for shift in range(1, line + 1):
					tex_line = tex[line - shift].rstrip()
					m = re_mpxerr.search(tex_line)
					if m:
						err["line"] = int(m.group("line")) + shift - 2
						err["file"] = os.path.join(self.pwd, m.group("file"))
						err["pkg"] = "TeX"
						yield err
						break

				if shift == line:
					# the error is in some verbatimtex
					yield err


class Dep (rubber.depend.Node):
	"""
	This class represents dependency nodes for MetaPost figures. The __init__
	method simply creates one node for the figures and one leaf node for all
	sources.
	"""
	def __init__ (self, set, target, source, context):
		self.cmd_pwd = os.path.dirname(source)
		super (Dep, self).__init__(set)
		self.add_product (target)
		self.include (os.path.basename (source))
		msg.log(_("%s is made from %r") % (target, self.sources))
		self.env = context['_environment']
		self.base = source[:-3]
		self.cmd = ["mpost", "\\batchmode;input %s" %
			os.path.basename(self.base)]
		if self.env.path == [""]:
			self.penv = {}
		else:
			path = string.join(self.env.path, ":")
			self.penv = {
				"TEXINPUTS": "%s:%s" % (path, os.getenv("TEXINPUTS", "")),
				"MPINPUTS": "%s:%s" % (path, os.getenv("MPINPUTS", "")) }
		self.log = None

	def include (self, source):
		"""
		This function tries to find a specified MetaPost source (currently all
		in the same directory), appends its actual name to the list, and
		parses it to find recursively included files.
		"""
		file = os.path.normpath(os.path.join(self.cmd_pwd, source))
		if os.path.exists(file + ".mp"):
			file = file + ".mp"
		elif not os.path.exists(file):
			return
		self.add_source (file)
		with open(file) as fd:
			for line in fd:
				m = re_input.search(line)
				if m:
					self.include (m.group ("file"))

	def run (self):
		"""
		Run Metapost from the source file's directory, so that figures are put
		next to their source file.
		"""
		msg.progress(_("running Metapost on %s") %
				msg.simplify(self.base + ".mp"))
		if self.env.execute(self.cmd, self.penv, pwd=self.cmd_pwd, kpse=1) == 0:
			return True

		# This creates a log file that has the same aspect as TeX logs.

		self.log = MPLogCheck(self.cmd_pwd)
		if not self.log.readlog (self.base + ".log", metapost_logfile_limit):
			msg.error(_(
				"I can't read MetaPost's log file, this is wrong."))
			return False
		return not self.log.errors()

	def get_errors (self):
		"""
		Report the errors from the last compilation.
		"""
		return self.log.get_errors()

	def clean (self):
		"""
		This method removes all the files that the Metapost compilation may
		have created. It is required because the compilation may produce more
		files than just the figures used by the document.
		"""
		super (Dep, self).clean ()
		base = self.base + "."
		ln = len(base)
		dir = os.path.dirname(base)
		if dir == "":
			list = os.listdir(".")
		else:
			list = os.listdir(dir)
		for f in list:
			file = os.path.join(dir, f)
			if file[:ln] == base:
				ext = file[ln:]
				m = re_mpext.match(ext)
				if m and ext[m.end():] == "":
					rubber.util.verbose_remove (file, pkg="mpost")

# The `files' dictionary associates dependency nodes to MetaPost sources. It
# is used to detect when several figures from the same source are included. It
# uses a global variable, and this is authentically BAD. Therefore it deserves
# a big fat huge FIXME. Graphics modules should proably be encapsuled in
# classes the same way as standard Rubber modules, that would help for this
# problem.

files = {}

def convert (source, target, context, set):
	if source in files:
		dep = files[source]
		dep.add_product(target)
	else:
		dep = Dep(set, target, source, context)
		files[source] = dep
	return dep
