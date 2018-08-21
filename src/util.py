# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# vim:noet:ts=4
"""
This module contains utility functions and classes used by the main system and
by the modules for various tasks.
"""

import hashlib
import os.path, stat, time
import errno
import imp
import re
import shutil
from string import whitespace
import sys

#-- Message writers --{{{1

# The function `_' is defined here to prepare for internationalization.
def _ (txt): return txt

class Message (object):
	"""
	All messages in the program are output using the `msg' object below.
	This class defines the interface for this object.

	Typical use:
	from rubber.messages import _, msg
	msg.log (_("Writing: %.").format (os.path.relpath (file)))
	"""
	def __init__ (self):
		self.level = 1
		self.write = sys.stderr.write
		self.short = 0
		self.pos = []

	def increase_verbosity (self):
		self.level += 1
	def decrease_verbosity (self):
		if 0 < self.level:
                        self.level -= 1
	def show_only_warnings (self):
		self.level = 0

	def write_to_stdout (self):
		self.write = sys.stdout.write

	def shorten_messages (self):
		self.short = 1

	def push_pos (self, pos):
		self.pos.append(pos)
	def pop_pos (self):
		del self.pos[-1]

	def display (self, kind, text, **info):
		"""
		Print an error or warning message. The argument 'kind' indicates the
		kind of message, among "error", "warning", "abort", the argument
		'text' is the main text of the message, the other arguments provide
		additional information, including the location of the error.
		"""
		if kind == "error":
			if text[0:13] == "LaTeX Error: ":
				text = text[13:]
			self.warn (text, **info)
			if "code" in info and info["code"] and not self.short:
				if "macro" in info:
					del info["macro"]
				self.warn (_("leading text: ") + info["code"], **info)

		elif kind == "abort":
			if self.short:
				msg = _("compilation aborted ") + info["why"]
			else:
				msg = _("compilation aborted: %s %s") % (text, info["why"])
			self.warn (msg, **info)

		elif kind == "warning":
			self.warn (text, **info)

	def error (self, text, **info):
		self.display(kind="error", text=text, **info)
	def warn (self, what, **where):
		if 0 <= self.level: self.write (self._format (where, what) + "\n")
	def progress (self, what, **where):
		if 1 <= self.level: self.write (self._format (where, what) + "\n")
	def info (self, what, **where):
		if 2 <= self.level: self.write (self._format (where, what) + "\n")
	def log (self, what, **where):
		if 3 <= self.level: self.write (self._format (where, what) + "\n")
	def debug (self, what, **where):
		if 4 <= self.level: self.write (self._format (where, what) + "\n")

	def _format (self, where, text):
		"""
		Format the given text into a proper error message, with file and line
		information in the standard format. Position information is taken from
		the dictionary given as first argument.
		"""
		if len(self.pos) > 0:
			if where is None or "file" not in where:
				where = self.pos[-1]
		elif where is None or where == {}:
			return text

		if "file" in where and where["file"] is not None:
			pos = os.path.relpath (where["file"])
			if "line" in where and where["line"]:
				pos = "%s:%d" % (pos, int(where["line"]))
				if "last" in where:
					if where["last"] != where["line"]:
						pos = "%s-%d" % (pos, int(where["last"]))
			pos = pos + ": "
		else:
			pos = ""
		if "macro" in where:
			text = "%s (in macro %s)" % (text, where["macro"])
		if "page" in where:
			text = "%s (page %d)" % (text, int(where["page"]))
		if "pkg" in where:
			text = "[%s] %s" % (where["pkg"], text)
		return pos + text

	def display_all (self, generator):
		something = 0
		for msg in generator:
			self.display(**msg)
			something = 1
		return something

msg = Message()

#-- Miscellaneous functions --{{{1

def md5_file (fname):
	"""
	Compute the MD5 sum of a given file.
	Returns None if the file does not exist.
	"""
	try:
		m = hashlib.md5()
		with open(fname, 'rb') as file:
			for line in file:
				m.update(line)
		return m.digest()
	except IOError as e:
		if e.errno == errno.ENOENT:
			return None
		raise e


#-- Keyval parsing --{{{1

re_keyval = re.compile("\
[ ,]*\
(?P<key>[^ \t\n{}=,]+)\
([ \n\t]*=[ \n\t]*\
(?P<val>({|[^{},]*)))?")

def parse_keyval (str):
	"""
	Parse a list of 'key=value' pairs, with the syntax used in LaTeX's
	standard 'keyval' package. The value returned is simply a dictionary that
	contains all definitions found in the string. For keys without a value,
	the dictionary associates the value None.
	If str is None, consider it as empty.
	"""
	dict = {}
	while str:
		m = re_keyval.match(str)
		if not m:
			break
		d = m.groupdict()
		str = str[m.end():]
		if not d["val"]:
			dict[d["key"]] = None
		elif d["val"] == '{':
			val, str = match_brace(str)
			dict[d["key"]] = val
		else:
			dict[d["key"]] = d["val"].strip()
	return dict

def match_brace (str):
	"""
	Split the string at the first closing brace such that the extracted prefix
	is balanced with respect to braces. The return value is a pair. If the
	adequate closing brace is found, the pair contains the prefix before the
	brace and the suffix after the brace (not containing the brace). If no
	adequate brace is found, return the whole string as prefix and an empty
	string as suffix.
	"""
	level = 0
	for pos in range(0, len(str)):
		if str[pos] == '{':
			level = level + 1
		elif str[pos] == '}':
			level = level - 1
			if level == -1:
				return (str[:pos], str[pos+1:])
	return (str, "")


#-- Checking for program availability --{{{1

checked_progs = {}

def prog_available (prog):
	"""
	Test whether the specified program is available in the current path, and
	return its actual path if it is found, or None.
	"""
	pathsep = ";" if os.name == "nt" else ":"
	fileext = ".exe" if os.name == "nt" else ""
	if prog in checked_progs:
		return checked_progs[prog]
	for path in os.getenv("PATH").split(pathsep):
		file = os.path.join(path, prog) + fileext
		if os.path.exists(file):
			st = os.stat(file)
			if stat.S_ISREG(st.st_mode) and (st.st_mode & 0o111):
				checked_progs[prog] = file
				return file
	checked_progs[prog] = None
	return None


#-- Variable handling --{{{1

class Variables:
	"""
	This class represent an environment containing variables. It can be
	accessed as a dictionary, except that every key must be declared using the
	constructor.

	Environments are stacked, i.e. each environment can have a parent
	environment that contains other variables. The variables declared in an
	environment take precedence over parent environments, but changing the
	value of a variable changes its value in the environment that actually
	defines it.
	"""

	def __init__ (self, parent = None, items = {}):
		"""
		Create an environment, possibly with a parent environment, and initial
		bindings.
		"""
		if parent is not None and not isinstance(parent, Variables):
			raise ValueError()
		self.parent = parent
		self.dict = items.copy ()

	def __getitem__ (self, key):
		"""
		Get the value of a variable in the environment or its parents.
		"""
		object = self
		while object is not None:
			if key in object.dict:
				return object.dict[key]
			object = object.parent
		raise KeyError (key)

	def __setitem__ (self, key, value):
		"""
		Set the value of a variable in the environment or its parents,
		assuming it is defined somewhere. Raises 'KeyError' if the variable is
		not declared.
		"""
		object = self
		while object is not None:
			if key in object.dict:
				object.dict[key] = value
				return
			object = object.parent
		raise KeyError (key)

	def to_dict (self):
		"""
		Construct a dict with the same keys and values,
		that can be  modified independently of self and its parents.
		"""
		result = {}
		object = self
		while object is not None:
			for key, value in object.dict.items():
				if key not in result:
					result[key] = value
			object = object.parent
		return result

	def __contains__ (self, key):
		object = self
		while object is not None:
			if key in object.dict:
				return True
			object = object.parent
		return False

#-- Parsing commands --{{{1

re_variable = re.compile("(?P<name>[a-zA-Z]+)")

def parse_line (line, dict):
	"""
	Decompose a string into a list of elements. The elements are separated by
	spaces, single and double quotes allow escaping of spaces (and quotes).
	Elements can contain variable references with the syntax '$VAR' (with only
	letters in the name) or '${VAR}'.

	If the argument 'dict' is defined, it is considered as a hash containing
	the values of the variables. If it is None, elements with variables are
	replaced by sequences of litteral strings or names, as follows:
		parse_line(" foo  bar${xy}quux toto  ")
			--> ["foo", ["'bar", "$xy", "'quux"], "toto"]
	"""
	elems = []
	i = 0
	size = len(line)
	while i < size:
		while i < size and line[i] in whitespace: i = i+1
		if i == size: break

		open = 0	# which quote is open
		arg = ""	# the current argument, so far
		if not dict: composed = None	# the current composed argument

		while i < size:
			c = line[i]

			# Open or close quotes.

			if c in '\'\"':
				if open == c: open = 0
				elif open: arg = arg + c
				else: open = c

			# '$' introduces a variable name, except within single quotes.

			elif c == '$' and open != "'":

				# Make the argument composed, if relevant.

				if not dict:
					if not composed: composed = []
					if arg != "": composed.append("'" + arg)
					arg = ""

				# Parse the variable name.

				if i+1 < size and line[i+1] == '{':
					end = line.find('}', i+2)
					if end < 0:
						name = line[i+2:]
						i = size
					else:
						name = line[i+2:end]
						i = end + 1
				else:
					m = re_variable.match(line, i+1)
					if m:
						name = m.group("name")
						i = m.end()
					else:
						name = ""
						i = i+1

				# Append the variable or its name.

				if dict:
					if name in dict:
						arg = arg + str(dict[name])
					# Send a warning for undefined variables ?
				else:
					composed.append("$" + name)
				continue

			# Handle spaces.

			elif c in whitespace:
				if open: arg = arg + c
				else: break
			else:
				arg = arg + c
			i = i+1

		# Append the new argument.

		if dict or not composed:
			elems.append(arg)
		else:
			if arg != "": composed.append("'" + arg)
			elems.append(composed)

	return elems

def explode_path (name = "PATH"):
	"""
	Parse an environment variable into a list of paths, and return it as an array.
	"""
	path = os.getenv (name)
	if path is not None:
		return path.split (":")
	else:
		return []

def find_resource (name, suffix = "", paths = []):
	"""
	find the indicated file, mimicking what latex would do:
	tries adding a suffix such as ".bib", or looking in the specified paths.
	if unsuccessful, returns None.
	"""
	name = name.strip ()

	if os.path.exists (name):
		return name
	elif suffix != "" and os.path.exists (name + suffix):
		return name + suffix

	for path in paths:
		fullname = os.path.join (path, name)
		if os.path.exists (fullname):
			return fullname
		elif suffix != "" and os.path.exists (fullname + suffix):
			return fullname + suffix

	return None

def verbose_remove (path, **kwargs):
	"""
	Remove a file and notify the user of it.
	This is meant for --clean;  failures are ignored.
	"""
	try:
		os.remove (path)
	except OSError as e:
		if e.errno != errno.ENOENT:
			msg.log (_("error removing '{filename}': {strerror}").format ( \
				filename=os.path.relpath (path), strerror=e.strerror), **kwargs)
		return
	msg.log (_("removing {filename}").format (filename=os.path.relpath (path)), **kwargs)

def verbose_rmtree (tree):
	"""
	Remove a directory and notify the user of it.
	This is meant for --clean;  failures are ignored.
	"""
	msg.log (_("removing tree {dirname}").format (dirname=os.path.relpath (tree)))
	# FIXME proper error reporting
	shutil.rmtree (tree, ignore_errors=True)

def abort_rubber_syntax_error ():
	"""signal invalid Rubber command-line"""
	sys.exit (1)

def abort_generic_error ():
	"""errors running LaTeX, finding essential files, etc."""
	sys.exit (2)
