# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# (c) Sebastian Kapfer 2015
# vim: noet:ts=4
"""
LaTeX document building system for Rubber.

This module contains all the code in Rubber that actually does the job of
building a LaTeX document from start to finish.
"""

import os, os.path, sys, imp
import re
import string

from rubber import _
from rubber.util import *
import rubber.depend
import rubber.latex_modules
import rubber.module_interface

from rubber.tex import EOF, OPEN, SPACE, END_LINE

#----  Module handler  ----{{{1

class Modules:
	"""
	This class gathers all operations related to the management of modules.
	The modules are	searched for first in the current directory, then as
	scripts in the 'modules' directory in the program's data directort, then
	as a Python module in the package `rubber.latex'.
	"""
	def __init__ (self, env):
		self.env = env
		self.objects = {}
		self.commands = {}

	def __getitem__ (self, name):
		"""
		Return the module object of the given name.
		"""
		return self.objects[name]

	def __contains__ (self, other):
		return other in self.objects

	def has_key (self, name):
		"""
		Check if a given module is loaded.
		"""
		return self.objects.has_key(name)

	def register (self, name, context={}):
		"""
		Attempt to register a module with the specified name. If the module is
		already loaded, do nothing. If it is found and not yet loaded, then
		load it, initialise it (using the context passed as optional argument)
		and run any delayed commands for it.
		"""
		if self.has_key(name):
			msg.debug(_("module %s already registered") % name, pkg='latex')
			return 2

		assert name != ''

		# First look for a script

		mod = None
		rub_searchpath = [
			"",                                # working dir
			rubber.latex_modules.__path__[0],  # builtin rubber modules
			# these are different from pre-1.4 search paths to avoid pulling
			# in old modules from previous installs.
			"/usr/local/share/rubber/latex_modules",
			"/usr/share/rubber/latex_modules",
			# FIXME allow the user to configure this, e.g. via RUBINPUTS
		]
		for path in rub_searchpath:
			file = os.path.join(path, name + ".rub")
			if os.path.exists(file):
				mod = ScriptModule(self.env, file)
				msg.log(_("script module %s registered") % name, pkg='latex')
				break

		# Then look for a Python module

		if not mod:
			f = None # so finally works even if find_module raises an exception
			try:
				(f, path, (suffix, mode, file_type)) = imp.find_module (
					name,
				rubber.latex_modules.__path__)
				if f == None or suffix != ".py" or file_type != imp.PY_SOURCE:
					raise ImportError
				source = imp.load_module (name, f, path, (suffix, mode, file_type))
			except ImportError:
				msg.debug(_("no support found for %s") % name, pkg='latex')
				return 0
			finally:
				if f != None:
					f.close ()
			if not (hasattr (source, "Module")
				and issubclass (source.Module, rubber.module_interface.Module)):
				msg.error (_("{}.Module must subclass rubber.module_interface.Module".format (name)))
				return 0

			mod = source.Module (document=self.env, context=context)
			msg.log (_("built-in module %s registered") % name, pkg='latex')

		# Run any delayed commands.

		if self.commands.has_key(name):
			for (cmd, args, vars) in self.commands[name]:
				msg.push_pos(vars)
				try:
					# put the variables as they were when the directive was
					# found
					saved_vars = self.env.vars
					self.env.vars = vars
					try:
						# call the command
						mod.command(cmd, args)
					finally:
						# restore the variables to their current state
						self.env.vars = saved_vars
				except AttributeError:
					msg.warn(_("unknown directive '%s.%s'") % (name, cmd))
				except TypeError:
					msg.warn(_("wrong syntax for '%s.%s'") % (name, cmd))
				msg.pop_pos()
			del self.commands[name]

		self.objects[name] = mod
		return 1

	def command (self, mod, cmd, args):
		"""
		Send a command to a particular module. If this module is not loaded,
		store the command so that it will be sent when the module is register.
		"""
		if self.objects.has_key(mod):
			self.objects[mod].command(cmd, args)
		else:
			if not self.commands.has_key(mod):
				self.commands[mod] = []
			self.commands[mod].append((cmd, args, self.env.vars))


#----  Log parser  ----{{{1

re_loghead = re.compile("This is [0-9a-zA-Z-]*")
re_file = re.compile("(\\((?P<file>[^ \n\t(){}]*)|\\))")
re_badbox = re.compile(r"(Ov|Und)erfull \\[hv]box ")
re_line = re.compile(r"(l\.(?P<line>[0-9]+)( (?P<code>.*))?$|<\*>)")
re_cseq = re.compile(r".*(?P<seq>(\\|\.\.\.)[^ ]*) ?$")
re_macro = re.compile(r"^(?P<macro>\\.*) ->")
re_page = re.compile("\[(?P<num>[0-9]+)\]")
re_atline = re.compile(
"( detected| in paragraph)? at lines? (?P<line>[0-9]*)(--(?P<last>[0-9]*))?")
re_reference = re.compile("LaTeX Warning: Reference `(?P<ref>.*)' \
on page (?P<page>[0-9]*) undefined on input line (?P<line>[0-9]*)\\.$")
re_label = re.compile("LaTeX Warning: (?P<text>Label .*)$")
re_warning = re.compile(
"(LaTeX|Package)( (?P<pkg>.*))? Warning: (?P<text>.*)$")
re_online = re.compile("(; reported)? on input line (?P<line>[0-9]*)")
re_ignored = re.compile("; all text was ignored after line (?P<line>[0-9]*).$")

class LogCheck (object):
	"""
	This class performs all the extraction of information from the log file.
	For efficiency, the instances contain the whole file as a list of strings
	so that it can be read several times with no disk access.
	"""
	#-- Initialization {{{2

	def __init__ (self):
		self.lines = None

	def readlog (self, name, limit):
		"""
		Read the specified log file, checking that it was produced by the
		right compiler. Returns False if the log file is invalid or does not
		exist.
		"""
		self.lines = None
		try:
			with open (name) as fp:
				line = fp.readline ()
				if not line or not re_loghead.match (line):
					msg.log (_('empty log'), pkg='latex')
					return False
				# do not read the whole log unconditionally
				whole_file = fp.read (limit)
				self.lines = whole_file.split ('\n')
				if fp.read (1) != '':
					# more data to be read
					msg.warn (_('log file is very long, and will not be read completely.'), pkg='latex')
			return True
		except IOError:
			msg.log (_('IO Error with log'), pkg='latex')
			return False

	#-- Process information {{{2

	def errors (self):
		"""
		Returns true if there was an error during the compilation.
		"""
		skipping = 0
		for line in self.lines:
			if line.strip() == "":
				skipping = 0
				continue
			if skipping:
				continue
			m = re_badbox.match(line)
			if m:
				skipping = 1
				continue
			if line[0] == "!":
				# We check for the substring "pdfTeX warning" because pdfTeX
				# sometimes issues warnings (like undefined references) in the
				# form of errors...

				if string.find(line, "pdfTeX warning") == -1:
					return 1
		return 0

	#-- Information extraction {{{2

	def continued (self, line):
		"""
		Check if a line in the log is continued on the next line. This is
		needed because TeX breaks messages at 79 characters per line. We make
		this into a method because the test is slightly different in Metapost.
		"""
		return len(line) == 79

	def parse (self, errors=0, boxes=0, refs=0, warnings=0):
		"""
		Parse the log file for relevant information. The named arguments are
		booleans that indicate which information should be extracted:
		- errors: all errors
		- boxes: bad boxes
		- refs: warnings about references
		- warnings: all other warnings
		The function returns a generator. Each generated item is a dictionary
		that contains (some of) the following entries:
		- kind: the kind of information ("error", "box", "ref", "warning")
		- text: the text of the error or warning
		- code: the piece of code that caused an error
		- file, line, last, pkg: as used by Message.format_pos.
		"""
		if not self.lines:
			return
		last_file = None
		pos = [last_file]
		page = 1
		parsing = 0    # 1 if we are parsing an error's text
		skipping = 0   # 1 if we are skipping text until an empty line
		something = 0  # 1 if some error was found
		prefix = None  # the prefix for warning messages from packages
		accu = ""      # accumulated text from the previous line
		macro = None   # the macro in which the error occurs
		cseqs = {}     # undefined control sequences so far
		for line in self.lines:
			# TeX breaks messages at 79 characters, just to make parsing
			# trickier...

			if not parsing and self.continued(line):
				accu += line
				continue
			line = accu + line
			accu = ""

			# Text that should be skipped (from bad box messages)

			if prefix is None and line == "":
				skipping = 0
				continue

			if skipping:
				continue

			# Errors (including aborted compilation)

			if parsing:
				if error == "Undefined control sequence.":
					# This is a special case in order to report which control
					# sequence is undefined.
					m = re_cseq.match(line)
					if m:
						seq = m.group("seq")
						if cseqs.has_key(seq):
							error = None
						else:
							cseqs[seq] = None
							error = "Undefined control sequence %s." % m.group("seq")
				m = re_macro.match(line)
				if m:
					macro = m.group("macro")
				m = re_line.match(line)
				if m:
					parsing = 0
					skipping = 1
					pdfTeX = string.find(line, "pdfTeX warning") != -1
					if error is not None and ((pdfTeX and warnings) or (errors and not pdfTeX)):
						if pdfTeX:
							d = {
								"kind": "warning",
								"pkg": "pdfTeX",
								"text": error[error.find(":")+2:]
							}
						else:
							d =	{
								"kind": "error",
								"text": error
							}
						d.update( m.groupdict() )
						m = re_ignored.search(error)
						if m:
							d["file"] = last_file
							if d.has_key("code"):
								del d["code"]
							d.update( m.groupdict() )
						elif pos[-1] is None:
							d["file"] = last_file
						else:
							d["file"] = pos[-1]
						if macro is not None:
							d["macro"] = macro
							macro = None
						yield d
				elif line[0] == "!":
					error = line[2:]
				elif line[0:3] == "***":
					parsing = 0
					skipping = 1
					if errors:
						yield	{
							"kind": "abort",
							"text": error,
							"why" : line[4:],
							"file": last_file
							}
				elif line[0:15] == "Type X to quit ":
					parsing = 0
					skipping = 0
					if errors:
						yield	{
							"kind": "error",
							"text": error,
							"file": pos[-1]
							}
				continue

			if len(line) > 0 and line[0] == "!":
				error = line[2:]
				parsing = 1
				continue

			if line == "Runaway argument?":
				error = line
				parsing = 1
				continue

			if line[:17] == "Output written on":
				continue

			# Long warnings

			if prefix is not None:
				if line[:len(prefix)] == prefix:
					text.append(string.strip(line[len(prefix):]))
				else:
					text = " ".join(text)
					m = re_online.search(text)
					if m:
						info["line"] = m.group("line")
						text = text[:m.start()] + text[m.end():]
					if warnings:
						info["text"] = text
						d = { "kind": "warning" }
						d.update( info )
						yield d
					prefix = None
				continue

			# Undefined references

			m = re_reference.match(line)
			if m:
				if refs:
					d =	{
						"kind": "warning",
						"text": _("Reference `%s' undefined.") % m.group("ref"),
						"file": pos[-1]
						}
					d.update( m.groupdict() )
					yield d
				continue

			m = re_label.match(line)
			if m:
				if refs:
					d =	{
						"kind": "warning",
						"file": pos[-1]
						}
					d.update( m.groupdict() )
					yield d
				continue

			# Other warnings

			if line.find("Warning") != -1:
				m = re_warning.match(line)
				if m:
					info = m.groupdict()
					info["file"] = pos[-1]
					info["page"] = page
					if info["pkg"] is None:
						del info["pkg"]
						prefix = ""
					else:
						prefix = ("(%s)" % info["pkg"])
					prefix = prefix.ljust(m.start("text"))
					text = [info["text"]]
				continue

			# Bad box messages

			m = re_badbox.match(line)
			if m:
				if boxes:
					mpos = { "file": pos[-1], "page": page }
					m = re_atline.search(line)
					if m:
						md = m.groupdict()
						for key in "line", "last":
							if md[key]: mpos[key] = md[key]
						line = line[:m.start()]
					d =	{
						"kind": "warning",
						"text": line
						}
					d.update( mpos )
					yield d
				skipping = 1
				continue

			# If there is no message, track source names and page numbers.

			last_file = self.update_file(line, pos, last_file)
			page = self.update_page(line, page)

	def get_errors (self):
		return self.parse(errors=1)
	def get_boxes (self):
		return self.parse(boxes=1)
	def get_references (self):
		return self.parse(refs=1)
	def get_warnings (self):
		return self.parse(warnings=1)

	def update_file (self, line, stack, last):
		"""
		Parse the given line of log file for file openings and closings and
		update the list `stack'. Newly opened files are at the end, therefore
		stack[1] is the main source while stack[-1] is the current one. The
		first element, stack[0], contains the value None for errors that may
		happen outside the source. Return the last file from which text was
		read (the new stack top, or the one before the last closing
		parenthesis).
		"""
		m = re_file.search(line)
		while m:
			if line[m.start()] == '(':
				last = m.group("file")
				stack.append(last)
			else:
				last = stack[-1]
				del stack[-1]
			line = line[m.end():]
			m = re_file.search(line)
		return last

	def update_page (self, line, before):
		"""
		Parse the given line and return the number of the page that is being
		built after that line, assuming the current page before the line was
		`before'.
		"""
		ms = re_page.findall(line)
		if ms == []:
			return before
		return int(ms[-1]) + 1

#----  Parsing and compiling  ----{{{1

re_command = re.compile("%[% ]*rubber: *(?P<cmd>[^ ]*) *(?P<arg>.*).*")

class SourceParser (rubber.tex.Parser):
	"""
	Extends the general-purpose TeX parser to handle Rubber directives in the
	comment lines.
	"""
	def __init__ (self, file, dep):
		super (SourceParser, self).__init__(file)
		self.latex_dep = dep

	def read_line (self):
		while rubber.tex.Parser.read_line(self):
			match = re_command.match(self.line.strip())
			if match is None:
				return True

			vars = dict(self.latex_dep.vars.items())
			vars['line'] = self.pos_line
			args = parse_line(match.group("arg"), vars)

			self.latex_dep.command(match.group("cmd"), args, vars)
		return False

	def skip_until (self, expr):
		regexp = re.compile(expr)
		while rubber.tex.Parser.read_line(self):
			match = regexp.match(self.line)
			if match is None:
				continue
			self.line = self.line[match.end():]
			self.pos_char += match.end()
			return

class EndDocument:
	""" This is the exception raised when \\end{document} is found. """
	pass

class EndInput:
	""" This is the exception raised when \\endinput is found. """
	pass

class LaTeXDep (rubber.depend.Node):
	"""
	This class represents dependency nodes for LaTeX compilation. It handles
	the cyclic LaTeX compilation until a stable output, including actual
	compilation (with a parametrable executable) and possible processing of
	compilation results (e.g. running BibTeX).

	Before building (or cleaning) the document, the method `parse' must be
	called to load and configure all required modules. Text lines are read
	from the files and parsed to extract LaTeX macro calls. When such a macro
	is found, a handler is searched for in the `hooks' dictionary. Handlers
	are called with one argument: the dictionary for the regular expression
	that matches the macro call.
	"""

	#--  Initialization  {{{2

	def __init__ (self, env, src, job):
		"""
		Initialize the environment. This prepares the processing steps for the
		given file (all steps are initialized empty) and sets the regular
		expressions and the hook dictionary.
		"""
		super (LaTeXDep, self).__init__(env.depends)
		self.env = env

		self.log = LogCheck()
		self.modules = Modules(self)

		self.vars = Variables(env.vars, {
			"program": "latex",
			"engine": "TeX",
			"paper": "",
			"arguments": [],
			"src-specials": "",
			"source": None,
			"target": None,
			"path": None,
			"base": None,
			"ext": None,
			"job": None,
			"logfile_limit": 1000000,
			"graphics_suffixes" : [] })

		self.cmdline = ["\\nonstopmode", "\\input{%s}"]

		# the initial hooks:

		self.hooks = {
			"begin": ("a", self.h_begin),
			"end": ("a", self.h_end),
			"pdfoutput": ("", self.h_pdfoutput),
			"input" : ("", self.h_input),
			"include" : ("a", self.h_include),
			"includeonly": ("a", self.h_includeonly),
			"usepackage" : ("oa", self.h_usepackage),
			"RequirePackage" : ("oa", self.h_usepackage),
			"documentclass" : ("oa", self.h_documentclass),
			"LoadClass" : ("oa", self.h_documentclass),
			# LoadClassWithOptions doesn't take optional arguments, but
			# we recycle the same handler
			"LoadClassWithOptions" : ("oa", self.h_documentclass),
			"tableofcontents" : ("", self.h_tableofcontents),
			"listoffigures" : ("", self.h_listoffigures),
			"listoftables" : ("", self.h_listoftables),
			"bibliography" : ("a", self.h_bibliography),
			"bibliographystyle" : ("a", self.h_bibliographystyle),
			"endinput" : ("", self.h_endinput)
		}
		self.begin_hooks = {
			"verbatim": self.h_begin_verbatim,
			"verbatim*": lambda loc: self.h_begin_verbatim(loc, env="verbatim\\*")
		}
		self.end_hooks = {
			"document": self.h_end_document
		}
		self.hooks_changed = True

		self.include_only = {}

		# FIXME interim solution for BibTeX module -- rewrite it.
		self.aux_files = []

		# description of the building process:

		self.onchange_md5 = {}
		self.onchange_cmd = {}
		self.removed_files = []

		# state of the builder:

		self.processed_sources = {}

		self.failed_module = None

		self.set_source (src, job)

	def set_source (self, path, jobname):
		"""
		Specify the main source for the document. The exact path and file name
		are determined, and the source building process is updated if needed,
		according the the source file's extension. The optional argument
		'jobname' can be used to specify the job name to something else that
		the base of the file name.
		"""
		assert os.path.exists(path)
		self.sources = []
		self.vars['source'] = path
		(src_path, name) = os.path.split(path)
		self.vars['path'] = src_path
		# derive jobname, which latex uses as the basename for all output
		(job, self.vars['ext']) = os.path.splitext(name)
		if jobname is None:
			self.set_job = 0
		else:
			self.set_job = 1
			job = jobname
		self.vars['job'] = job
		if src_path == "":
			src_path = "."
			self.vars['base'] = job
		else:
			self.env.path.append(src_path)
			self.vars['base'] = os.path.join(src_path, job)

		source = path
		prefix = os.path.join(self.vars["cwd"], "")
		if source[:len(prefix)] == prefix:
			comp_name = source[len(prefix):]
		else:
			comp_name = source
		if comp_name.find('"') >= 0:
			msg.error(_("The filename contains \", latex cannot handle this."))
			return 1
		for c in " \n\t()":
			if source.find(c) >= 0:
				msg.warn(_("Source path uses special characters, error tracking might get confused."))
				break

		self.add_product (self.basename (with_suffix=".dvi"))
		self.add_product (self.basename (with_suffix=".log"))

		# always expect a primary aux file
		self.new_aux_file (self.basename (with_suffix=".aux"))
		self.add_product (self.basename (with_suffix=".synctex.gz"))

		return 0

	def basename (self, with_suffix=""):
		return self.vars["job"] + with_suffix

	def set_primary_product_suffix (self, suffix=".dvi"):
		"""Change the suffix of the primary product"""
		del self.set[self.products[0]]
		self.products[0] = self.basename (with_suffix=suffix)
		self.add_product (self.products[0])

	def new_aux_file (self, aux_file):
		"""Register a new latex .aux file"""
		self.add_source (aux_file, track_contents=True)
		self.add_product (aux_file)
		self.aux_files.append (aux_file)

	def includeonly (self, files):
		"""
		Use partial compilation, by appending a call to \\includeonly on the
		command line on compilation.
		"""
		if self.vars["engine"] == "VTeX":
			msg.error(_("I don't know how to do partial compilation on VTeX."))
			return
		if self.cmdline[-2][:13] == "\\includeonly{":
			self.cmdline[-2] = "\\includeonly{" + ",".join(files) + "}"
		else:
			self.cmdline.insert(-1, "\\includeonly{" + ",".join(files) + "}")
		for f in files:
			self.include_only[f] = None

	def source (self):
		"""
		Return the main source's complete filename.
		"""
		return self.vars['source']

	#--  LaTeX source parsing  {{{2

	def parse (self):
		"""
		Parse the source for packages and supported macros.
		"""
		try:
			self.process(self.source())
		except EndDocument:
			pass
		msg.log(_("dependencies: %r") % self.sources, pkg='latex')

	def parse_file (self, file):
		"""
		Process a LaTeX source. The file must be open, it is read to the end
		calling the handlers for the macro calls. This recursively processes
		the included sources.
		"""
		parser = SourceParser(file, self)
		parser.set_hooks(self.hooks.keys())
		self.hooks_changed = False
		while True:
			if self.hooks_changed:
				parser.set_hooks(self.hooks.keys())
				self.hooks_changed = False
			token = parser.next_hook()
			if token.cat == EOF:
				break
			format, function = self.hooks[token.val]
			args = []
			for arg in format:
				if arg == '*':
					args.append(parser.get_latex_star())
				elif arg == 'a':
					args.append(parser.get_argument_text())
				elif arg == 'o':
					args.append(parser.get_latex_optional_text())
			self.parser = parser
			self.vars['line'] = parser.pos_line
			function(self.vars, *args)

	def process (self, path):
		"""
		This method is called when an included file is processed. The argument
		must be a valid file name.
		"""
		if self.processed_sources.has_key(path):
			msg.debug(_("%s already parsed") % path, pkg='latex')
			return
		self.processed_sources[path] = None
		if path not in self.sources:
			self.add_source(path)

		try:
			saved_vars = self.vars
			try:
				msg.log(_("parsing %s") % path, pkg='latex')
				self.vars = Variables(saved_vars,
					{ "file": path, "line": None })
				file = open(path)
				try:
					self.parse_file(file)
				finally:
					file.close()

			finally:
				self.vars = saved_vars
				msg.debug(_("end of %s") % path, pkg='latex')

		except EndInput:
			pass

	def input_file (self, name, loc={}):
		"""
		Treat the given name as a source file to be read. If this source can
		be the result of some conversion, then the conversion is performed,
		otherwise the source is parsed. The returned value is a couple
		(name,dep) where `name' is the actual LaTeX source and `dep' is
		its dependency node. The return value is (None,None) if the source
		could neither be read nor built.
		"""
		if name.find("\\") >= 0 or name.find("#") >= 0:
			return None, None

		for path in self.env.path:
			pname = os.path.join(path, name)
			dep = self.env.convert(pname, suffixes=[".tex",""], context=self.vars)
			if dep:
				file = dep.products[0]
			else:
				file = self.env.find_file(name, ".tex")
				if not file:
					continue
				dep = None
			self.add_source(file)

			if dep is None or dep.is_leaf():
				self.process(file)

			if dep is None:
				return file, self.set[file]
			else:
				return file, dep

		return None, None

	#--  Directives  {{{2

	def command (self, cmd, args, pos=None):
		"""
		Execute the rubber command 'cmd' with arguments 'args'. This is called
		when a command is found in the source file or in a configuration file.
		A command name of the form 'foo.bar' is considered to be a command
		'bar' for module 'foo'. The argument 'pos' describes the position
		(file and line) where the command occurs.
		"""
		if pos is None:
			pos = self.vars
		# Calls to this method are actually translated into calls to "do_*"
		# methods, except for calls to module directives.
		lst = string.split(cmd, ".", 1)
		#try:
		if len(lst) > 1:
			self.modules.command(lst[0], lst[1], args)
		elif not hasattr(self, "do_" + cmd):
			msg.warn(_("unknown directive '%s'") % cmd, **pos)
		else:
			msg.log(_("directive: %s") % ' '.join([cmd]+args), pkg='latex')
			getattr(self, "do_" + cmd)(*args)
		#except TypeError:
		#	msg.warn(_("wrong syntax for '%s'") % cmd, **pos)

	def do_alias (self, name, val):
		if self.hooks.has_key(val):
			self.hooks[name] = self.hooks[val]
			self.hooks_changed = True

	def do_clean (self, *args):
		for file in args:
			self.removed_files.append(file)

	def do_depend (self, *args):
		for arg in args:
			file = self.env.find_file(arg)
			if file:
				self.add_source(file)
			else:
				msg.warn(_("dependency '%s' not found") % arg, **self.vars)

	def do_make (self, file, *args):
		vars = { "target": file }
		while len(args) > 1:
			if args[0] == "from":
				vars["source"] = args[1]
			elif args[0] == "with":
				vars["name"] = args[1]
			else:
				break
			args = args[2:]
		if len(args) != 0:
			msg.error(_("invalid syntax for 'make'"), **self.vars)
			return
		self.env.conv_set(file, vars)

	def do_module (self, mod, opt=None):
		self.modules.register (mod, context = {'arg':mod, 'opt':opt})

	def do_onchange (self, file, cmd):
		self.onchange_cmd[file] = cmd
		self.onchange_md5[file] = md5_file(file)

	def do_paper (self, arg):
		self.vars["paper"] = arg

	def do_path (self, name):
		self.env.path.append(name)

	def do_read (self, name):
		saved_vars = self.vars
		try:
			self.vars = Variables (self.vars,
					{ "file": name, "line": None })
			with open(name) as file:
				lineno = 0
				for line in file:
					lineno += 1
					line = line.strip()
					if line == "" or line[0] == "%":
						continue
					self.vars["line"] = lineno
					lst = parse_line(line, self.vars)
					self.command(lst[0], lst[1:])
		except IOError:
			msg.warn(_("cannot read option file %s") % name, **self.vars)
		finally:
			self.vars = saved_vars

	def do_rules (self, file):
		name = self.env.find_file(file)
		if name is None:
			msg.warn(_("cannot read rule file %s") % file, **self.vars)
		else:
			self.env.converter.read_ini(name)

	def do_set (self, name, val):
		try:
			if type (self.vars[name]) is list:
				msg.warn (_("cannot set list-type variable to scalar: set %s %s (ignored; use setlist, not set)") % (name, val))
				return
			if type (self.vars[name]) is int:
				try:
					val = int (val)
				except:
					msg.warn (_("cannot set int variable %s to value %s (ignored)") % (name, val))
					return
			self.vars[name] = val
		except KeyError:
			msg.warn(_("unknown variable: %s") % name, **self.vars)

	def do_shell_escape (self):
		self.env.doc_requires_shell_ = True

	def do_synctex (self):
		self.env.synctex = True

	def do_setlist (self, name, *val):
		try:
			self.vars[name] = list(val)
		except KeyError:
			msg.warn(_("unknown variable: %s") % name, **self.vars)

	def do_produce (self, *args):
		for arg in args:
			self.add_product(arg)

	def do_watch (self, *args):
		for arg in args:
			self.watch_file(arg)

	#--  Macro handling  {{{2

	def hook_macro (self, name, format, fun):
		self.hooks[name] = (format, fun)
		self.hooks_changed = True

	def hook_begin (self, name, fun):
		self.begin_hooks[name] = fun

	def hook_end (self, name, fun):
		self.end_hooks[name] = fun

	# Now the macro handlers:

	def h_begin (self, loc, env):
		if self.begin_hooks.has_key(env):
			self.begin_hooks[env](loc)

	def h_end (self, loc, env):
		if self.end_hooks.has_key(env):
			self.end_hooks[env](loc)

	def h_pdfoutput (self, loc):
		"""
		Called when \\pdfoutput is found. Tries to guess if it is a definition
		that asks for the output to be in PDF or DVI.
		"""
		parser = self.parser
		token = parser.get_token()
		if token.raw == '=':
			token2 = parser.get_token()
			if token2.raw == '0':
				mode = 0
			elif token2.raw == '1':
				mode = 1
			else:
				parser.put_token(token2)
				return
		elif token.raw == '0':
			mode = 0
		elif token.raw == '1':
			mode = 1
		else:
			parser.put_token(token)
			return

		if mode == 0:
			if 'pdftex' in self.modules:
				self.modules['pdftex'].mode_dvi()
			else:
				self.modules.register('pdftex', {'opt': 'dvi'})
		else:
			if 'pdftex' in self.modules:
				self.modules['pdftex'].mode_pdf()
			else:
				self.modules.register('pdftex')

	def h_input (self, loc):
		"""
		Called when an \\input macro is found. This calls the `process' method
		if the included file is found.
		"""
		token = self.parser.get_token()
		if token.cat == OPEN:
			file = self.parser.get_group_text()
		else:
			file = ""
			while token.cat not in (EOF, SPACE, END_LINE):
				file += token.raw
				token = self.parser.get_token()
		self.input_file(file, loc)

	def h_include (self, loc, filename):
		"""
		Called when an \\include macro is found. This includes files into the
		source in a way very similar to \\input, except that LaTeX also
		creates .aux files for them, so we have to notice this.
		"""
		if self.include_only and not self.include_only.has_key(filename):
			return
		file, _ = self.input_file(filename, loc)
		if file:
			self.new_aux_file (filename + ".aux")

	def h_includeonly (self, loc, files):
		"""
		Called when the macro \\includeonly is found, indicates the
		comma-separated list of files that should be included, so that the
		othe \\include are ignored.
		"""
		self.include_only = {}
		for name in files.split(","):
			name = name.strip()
			if name != "":
				self.include_only[name] = None

	def h_documentclass (self, loc, opt, name):
		"""
		Called when the macro \\documentclass is found. It almost has the same
		effect as `usepackage': if the source's directory contains the class
		file, in which case this file is treated as an input, otherwise a
		module is searched for to support the class.
		"""
		file = self.env.find_file(name + ".cls")
		if file:
			self.process(file)
		else:
			self.modules.register (name,
				context = Variables (self.vars, {'opt': opt}))

	def h_usepackage (self, loc, opt, names):
		"""
		Called when a \\usepackage macro is found. If there is a package in the
		directory of the source file, then it is treated as an include file
		unless there is a supporting module in the current directory,
		otherwise it is treated as a package.
		"""
		for name in string.split(names, ","):
			name = name.strip()
			if name == '': continue  # \usepackage{a,}
			file = self.env.find_file(name + ".sty")
			if file and not os.path.exists(name + ".py"):
				self.process(file)
			else:
				self.modules.register (name,
					context = Variables (self.vars, {'opt':opt}))

	def h_tableofcontents (self, loc):
		self.add_product(self.basename (with_suffix=".toc"))
		self.add_source(self.basename (with_suffix=".toc"), track_contents=True)
	def h_listoffigures (self, loc):
		self.add_product(self.basename (with_suffix=".lof"))
		self.add_source(self.basename (with_suffix=".lof"), track_contents=True)
	def h_listoftables (self, loc):
		self.add_product(self.basename (with_suffix=".lot"))
		self.add_source(self.basename (with_suffix=".lot"), track_contents=True)

	def h_bibliography (self, loc, names):
		"""
		Called when the macro \\bibliography is found. This method actually
		registers the module bibtex (if not already done) and registers the
		databases.
		"""
		self.modules.register ("bibtex")
		# This registers the actual hooks, so that subsequent occurrences of
		# \bibliography and \bibliographystyle will be caught by the module.
		# However, the first time, we have to call the hooks from here. The
		# line below assumes that the new hook has the same syntax.
		self.hooks['bibliography'][1](loc, names)

	def h_bibliographystyle (self, loc, name):
		"""
		Called when \\bibliographystyle is found. This registers the module
		bibtex (if not already done) and calls the method set_style() of the
		module.
		"""
		self.modules.register ("bibtex")
		# The same remark as in 'h_bibliography' applies here.
		self.hooks['bibliographystyle'][1](loc, name)

	def h_begin_verbatim (self, loc, env="verbatim"):
		"""
		Called when \\begin{verbatim} is found. This disables all macro
		handling and comment parsing until the end of the environment. The
		optional argument 'end' specifies the end marker, by default it is
		"\\end{verbatim}".
		"""
		self.parser.skip_until(r"[ \t]*\\end\{%s\}.*" % env)

	def h_endinput (self, loc):
		"""
		Called when \\endinput is found. This stops the processing of the
		current input file, thus ignoring any code that appears afterwards.
		"""
		raise EndInput

	def h_end_document (self, loc):
		"""
		Called when \\end{document} is found. This stops the processing of any
		input file, thus ignoring any code that appears afterwards.
		"""
		raise EndDocument

	#--  Compilation steps  {{{2

	def compile (self):
		"""
		Run one LaTeX compilation on the source. Return true on success or
		false if errors occured.
		"""
		msg.progress(_("compiling %s") % msg.simplify(self.source()))

		file = self.source()

		prefix = os.path.join(self.vars["cwd"], "")
		if file[:len(prefix)] == prefix:
			file = file[len(prefix):]
		if file.find(" ") >= 0:
			file = '"%s"' % file

		cmd = [self.vars["program"]]

		if self.set_job:
			if self.vars["engine"] == "VTeX":
				msg.error(_("I don't know how set the job name with %s.")
					% self.vars["engine"])
			else:
				cmd.append("-jobname=" + self.vars["job"])

		specials = self.vars["src-specials"]
		if specials != "":
			if self.vars["engine"] == "VTeX":
				msg.warn(_("I don't know how to make source specials with %s.")
					% self.vars["engine"])
				self.vars["src-specials"] = ""
			elif specials == "yes":
				cmd.append("-src-specials")
			else:
				cmd.append("-src-specials=" + specials)

		if self.env.is_in_unsafe_mode_:
			cmd += [ '--shell-escape' ]
		elif self.env.doc_requires_shell_:
			msg.error (_("the document tries to run external programs which could be dangerous.  use rubber --unsafe if the document is trusted."))

		if self.env.synctex:
			cmd += [ "-synctex=1" ]

		# make sure the arguments actually are a list, otherwise the
		# characters of the string might be passed as individual arguments
		assert type (self.vars["arguments"]) is list
		# arguments inserted by the document allowed only in unsafe mode, since
		# this could do arbitrary things such as enable shell escape (write18)
		if self.env.is_in_unsafe_mode_:
			cmd += self.vars["arguments"]
		elif len (self.vars["arguments"]) > 0:
			msg.error (_("the document tries to modify the LaTeX command line which could be dangerous.  use rubber --unsafe if the document is trusted."))

		cmd += [x.replace("%s",file) for x in self.cmdline]

		# Remove the CWD from elements inthe path, to avoid potential problems
		# with special characters if there are any (except that ':' in paths
		# is not handled).

		prefix = self.env.vars["cwd"]
		prefix_ = os.path.join(prefix, "")
		paths = []
		for p in self.env.path:
			if p == prefix:
				paths.append(".")
			elif p[:len(prefix_)] == prefix_:
				paths.append("." + p[len(prefix):])
			else:
				paths.append(p)
		inputs = string.join(paths, ":")

		if inputs == "":
			env = {}
		else:
			inputs = inputs + ":" + os.getenv("TEXINPUTS", "")
			env = {"TEXINPUTS": inputs}

		self.env.execute(cmd, env, kpse=1)

		if not self.parse_log ():
			msg.error(_("Running %s failed.") % cmd[0])
			return False
		if self.log.errors():
			return False
		if not os.access(self.products[0], os.F_OK):
			msg.error(_("Output file `%s' was not produced.") %
				msg.simplify(self.products[0]))
			return False
		return True

	def parse_log (self):
		logfile_name = self.basename (with_suffix=".log")
		logfile_limit = self.vars["logfile_limit"]
		return self.log.readlog (logfile_name, logfile_limit)

	def pre_compile (self):
		"""
		Prepare the source for compilation using package-specific functions.
		This function must return False on failure.
		"""
		msg.log(_("building additional files..."), pkg='latex')

		for mod in self.modules.objects.values():
			if not mod.pre_compile():
				self.failed_module = mod
				return False
		return True

	def post_compile (self):
		"""
		Run the package-specific operations that are to be performed after
		each compilation of the main source. Returns true on success or false
		on failure.
		"""
		msg.log(_("running post-compilation scripts..."), pkg='latex')

		for file, md5 in self.onchange_md5.items():
			new = md5_file(file)
			if md5 != new:
				self.onchange_md5[file] = new
				if new != None:
					msg.progress(_("running %s") % self.onchange_cmd[file])
					# FIXME portability issue: explicit reference to shell
					self.env.execute(["sh", "-c", self.onchange_cmd[file]])

		for mod in self.modules.objects.values():
			if not mod.post_compile():
				self.failed_module = mod
				return False
		return True

	def clean (self):
		"""
		Remove all files that are produced by compilation.
		"""
		super (LaTeXDep, self).clean ()
		for file in self.removed_files:
			rubber.util.verbose_remove (file, pkg = "latex")
		msg.log(_("cleaning additional files..."), pkg='latex')
		for mod in self.modules.objects.values():
			mod.clean()

	#--  Building routine  {{{2

	def run (self):
		"""
		Run the building process until the last compilation, or stop on error.
		This method supposes that the inputs were parsed to register packages
		and that the LaTeX source is ready. If the second (optional) argument
		is true, then at least one compilation is done. As specified by the
		parent class, the method returns True on success and False on
		failure.
		"""
		if not self.pre_compile():
			return False

		# If an error occurs after this point, it will be while LaTeXing.
		self.failed_dep = self
		self.failed_module = None

		if not self.compile():
			return False
		if not self.post_compile():
			return False

		# Finally there was no error.
		self.failed_dep = None

		return True

	#--  Utility methods  {{{2

	def get_errors (self):
		if self.failed_module is None:
			return self.log.get_errors()
		else:
			return self.failed_module.get_errors()

	def watch_file (self, filename):
		"""
		Register the given file (typically "jobname.toc" or such) to be
		watched. When the file changes during a compilation, it means that
		another compilation has to be done.
		"""
		self.add_source (filename, track_contents=True)

	def remove_suffixes (self, list):
		"""
		Remove all files derived from the main source with one of the
		specified suffixes.
		"""
		for suffix in list:
			file = self.basename (with_suffix=suffix)
			rubber.util.verbose_remove (file, pkg = "latex")

class ScriptModule (rubber.module_interface.Module):
	# TODO: the constructor is not conformant with the one of the parent class.
	"""
	This class represents modules that are defined as Rubber scripts.
	"""
	def __init__ (self, env, filename):
		vars = Variables(env.vars, {
			'file': filename,
			'line': None })
		lineno = 0
		with open(filename) as file:
			for line in file:
				line = line.strip()
				lineno = lineno + 1
				if line == "" or line[0] == "%":
					continue
				vars['line'] = lineno
				lst = parse_line(line, vars)
				env.command(lst[0], lst[1:], vars)
