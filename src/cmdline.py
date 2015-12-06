# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# (c) Sebastian Kapfer, 2015
# vim: noet:ts=4
"""
This is the command line interface for Rubber.
"""

import os
import os.path
import sys
import string
from getopt import getopt, GetoptError
import shutil
import tempfile

import rubber.converters.compressor
from rubber.environment import Environment
from rubber.depend import ERROR, CHANGED, UNCHANGED
from rubber.util import _, msg
import rubber.util
from rubber.version import version as rubber_version

class Main (object):
	def __init__ (self, mode):
		self.rubber_mode = mode  # can be "build", "clean", "info" or "pipe"
		self.max_errors = 10
		msg.write = rubber.util.stderr_write

		self.place = "."
		self.path = []
		self.prologue = []
		self.epilogue = []
		self.include_only = None
		self.compress = None
		self.jobname = None
		self.unsafe = False

		# FIXME when are these legal
		self.warn = 0
		self.warn_boxes = 0
		self.warn_misc = 0
		self.warn_refs = 0

	def short_help (self):
		"""
		Display a short description of the command line.
		"""
		sys.stderr.write (_("""\
usage: rubber [options] sources...
For more information, try `rubber --help'.
"""))
		rubber.util.abort_rubber_syntax_error ()

	def ignored_option (self, opt):
		msg.warn (_("warning: ignoring option %s") % opt)

	def illegal_option (self, opt):
		msg.error (_("error: illegal option %s") % opt)
		rubber.util.abort_rubber_syntax_error ()

	def help (self):
		"""
		Display the description of all the options and exit.
		"""
		sys.stderr.write (_("""\
This is Rubber version %s.
usage: rubber [options] sources...
available options:
  -b, --bzip2              compress the final document with bzip2
      --clean              remove produced files instead of compiling
  -c, --command=CMD        run the directive CMD before parsing (see man page)
  -e, --epilogue=CMD       run the directive CMD after parsing
  -f, --force              force at least one compilation
  -z, --gzip               compress the final document
  -h, --help               display this help
      --inplace            compile the documents from their source directory
      --into=DIR           go to directory DIR before compiling
      --jobname=NAME       set the job name for the first target
  -l, --landscape          change paper orientation (if relevant)
  -n, --maxerr=NUM         display at most NUM errors (default: 10)
  -m, --module=MOD[:OPTS]  use module MOD (with options OPTS)
      --only=SOURCES       only include the specified SOURCES
  -o, --post=MOD[:OPTS]    postprocess with module MOD (with options OPTS)
  -d, --pdf                produce a pdf (synonym for -m pdftex or -o ps2pdf)
  -p, --ps                 process through dvips (synonym for -o dvips)
  -q, --quiet              suppress messages
  -r, --read=FILE          read additional directives from FILE
  -S, --src-specials       enable insertion of source specials
      --synctex            enable SyncTeX support
      --unsafe             permits the document to run external commands
  -s, --short              display errors in a compact form
  -I, --texpath=DIR        add DIR to the search path for LaTeX
  -v, --verbose            increase verbosity
      --version            print version information and exit
  -W, --warn=TYPE          report warnings of the given TYPE (see man page)
""") % rubber.version.version)

	def parse_opts (self, cmdline):
		"""
		Parse the command-line arguments.
		Returns the extra arguments (i.e. the files to operate on), or an
		empty list, if no extra arguments are present.
		"""
		# if no arguments at all are given, print a short version of the
		# help text and exit.
		if cmdline == []:
			self.short_help ()
		try:
			opts, args = getopt(
				cmdline, "I:bc:de:fhklm:n:o:pqr:SsvW:z",
				["bzip2", "cache", "clean", "command=", "epilogue=", "force", "gzip",
				 "help", "inplace", "into=", "jobname=", "keep", "landscape", "maxerr=",
				 "module=", "only=", "post=", "pdf", "ps", "quiet", "read=",
				 "readopts=",
				 "src-specials", "shell-escape", "synctex", "unsafe", "short", "texpath=", "verbose", "version",
				 "boxes", "check", "deps", "errors", "refs", "rules", "warnings",
				 "warn="])
		except GetoptError as e:
			msg.error (_("getopt error: %s") % str (e))
			rubber.util.abort_rubber_syntax_error ()

		extra = []
		using_dvips = False

		for (opt,arg) in opts:
			# obsolete options
			if opt == "--cache":
				# unimplemented option (harmless)
				self.ignored_option (opt)
			elif opt == "--readopts":
				# undocumented option which is no longer supported
				self.illegal_option (opt)

			# info
			elif opt in ("-h", "--help"):
				self.help ()
				exit (0)
			elif opt == "--version":
				sys.stdout.write ("Rubber version: %s\n" % \
					rubber_version)
				exit (0)

			# mode of operation
			elif opt == "--clean":
				self.ignored_option (opt)
			elif opt in ("-k", "--keep"):
				if self.rubber_mode == "pipe":
					self.keep_temp = True
				else:
					# does not make any sense except in pipe mode
					self.illegal_option (opt)

			# compression etc. which affects which products exist
			elif opt in ("-b", "--bzip2", "-z", "--gzip"):
				algo = "bzip2" if opt in ("-b", "--bzip2") else "gzip"
				if self.compress is not None and self.compress != algo:
					self.ignored_option (opt)
				else:
					self.compress = algo
			elif opt in ("-c", "--command"):
				self.prologue.append(arg)
			elif opt in ("-e", "--epilogue"):
				self.epilogue.append(arg)
			elif opt in ("-f", "--force"):
				self.force = True
			elif opt == "--inplace":
				self.place = None
			elif opt == "--into":
				self.place = arg
			elif opt == "--jobname":
				self.jobname = arg
			elif opt in ("-l", "--landscape"):
				self.prologue.append("paper landscape")
			elif opt in ("-n", "--maxerr"):
				self.max_errors = int(arg)
			elif opt in ("-m", "--module"):
				self.prologue.append("module " +
					string.replace(arg, ":", " ", 1))
			elif opt == "--only":
				self.include_only = arg.split(",")
			elif opt in ("-o", "--post"):
				if self.rubber_mode == "info":
					self.illegal_option (opt)
				self.epilogue.append("module " +
					string.replace(arg, ":", " ", 1))
			elif opt in ("-d", "--pdf"):
				if using_dvips:
					self.epilogue.append("module ps2pdf")
				else:
					self.prologue.append("module pdftex")
			elif opt in ("-p", "--ps"):
				self.epilogue.append("module dvips")
				using_dvips = True
			elif opt in ("-q", "--quiet"):
				msg.level = msg.level - 1
			# we continue to accept --shell-escape for now
			elif opt in ("--unsafe", "--shell-escape"):
				self.unsafe = True
			elif opt in ("-r" ,"--read"):
				self.prologue.append("read " + arg)
			elif opt in ("-S", "--src-specials"):
				self.prologue.append("set src-specials yes")
			elif opt in ("-s", "--short"):
				msg.short = 1
			elif opt in ("--synctex"):
				self.prologue.append("synctex")
			elif opt in ("-I", "--texpath"):
				self.path.append(arg)
			elif opt in ("-v", "--verbose"):
				msg.level = msg.level + 1
			elif opt in ("-W", "--warn"):
				self.warn = 1
				if arg == "all":
					self.warn_boxes = 1
					self.warn_misc = 1
					self.warn_refs = 1
				if arg == "boxes":
					self.warn_boxes = 1
				elif arg == "misc":
					self.warn_misc = 1
				elif arg == "refs":
					self.warn_refs = 1
			elif opt in ("--boxes", "--check", "--deps", "--errors", "--refs", "--rules", "--warnings"):
				if self.rubber_mode != "info":
					self.illegal_option (opt)
				if self.info_action is not None:
					msg.error (_("error: cannot have both '--%s' and '%s'") \
						% (self.info_action, opt))
					rubber.util.abort_rubber_syntax_error ()
				self.info_action = opt[2:]

			elif arg == "":
				extra.append(opt)
			else:
				extra.extend([arg, opt])

		ret = extra + args

		if self.jobname is not None and len (ret) > 1:
			msg.error (_("error: cannot give jobname and have more than one input file"))
			rubber.util.abort_rubber_syntax_error ()

		return ret

	def prepare_source (self, filename):
		"""
		Prepare the dependency node for the main LaTeX run.
		Returns the filename of the main LaTeX source file, which might
		change for various reasons (adding a .tex suffix; preprocessors;
		pipe dumping).
		When this is done, the file must exist on disk, otherwise this
		function must exit(1) or exit(2).
		"""
		path = rubber.util.find_resource (filename, suffix=".tex")

		if not path:
			msg.error (_("Main document not found: '%s'") % filename)
			rubber.util.abort_generic_error ()

		base, ext = os.path.splitext (path)

		from rubber.converters.literate import literate_preprocessors as lpp
		if ext in lpp.keys ():
			src = base + ".tex"
			# FIXME kill src_node
			src_node = lpp[ext] (self.env.depends, src, path)
			if self.rubber_mode == "build":
				if not self.unsafe:
					msg.error (_("Running external commands requires --unsafe."))
					rubber.util.abort_rubber_syntax_error ()
				# Produce the source from its dependency rules, if needed.
				if src_node.make () == ERROR:
					msg.error (_("Producing the main LaTeX file failed: '%s'") \
						% src)
					rubber.util.abort_generic_error ()
		else:
			src = path

		from rubber.converters.latex import LaTeXDep
		self.env.final = self.env.main = LaTeXDep (self.env, src, self.jobname)

		return src

	def main (self, cmdline):
		"""
		Run Rubber for the specified command line. This processes each
		specified source in order (for making or cleaning). If an error
		happens while making one of the documents, the whole process stops.
		The method returns the program's exit code.
		"""
		args = self.parse_opts (cmdline)

		initial_dir = os.getcwd()
		msg.cwd = os.path.join(initial_dir, "")

		if self.place == ".":
			self.place = initial_dir

		if self.place is not None:
			msg.path = self.place
			self.place = os.path.abspath(self.place)

		global rubber
		msg.log (_("This is Rubber version %s.") % rubber_version)

		for srcname in args:
			src = os.path.join(initial_dir, srcname)

			# Go to the appropriate directory
			try:
				if self.place != ".":
					if self.place is None:
						msg.path = os.path.dirname(src)
						os.chdir(os.path.dirname(src))
					else:
						os.chdir(self.place)
			except OSError as e:
				msg.error(_("Error changing to working directory: %s") % e.strerror)
				rubber.util.abort_generic_error ()

			# prepare the source file.  this may require a pre-processing
			# step, or dumping stdin.  thus, the input filename may change.
			# in case of build mode, preprocessors will be run as part of
			# prepare_source.
			env = self.env = Environment ()
			self.env.is_in_unsafe_mode_ = self.unsafe
			src = self.prepare_source (src)

			if self.include_only is not None:
				env.main.includeonly (self.include_only)

			# at this point, the LaTeX source file must exist; if it is
			# the result of pre-processing, this has happened already.
			# the main LaTeX file is not found via find_file (unlike
			# most other resources) by design:  paths etc may be set up
			# from within via rubber directives, so that wouldn't make a
			# whole lot of sense.
			if not os.path.exists (src):
				msg.error (_("LaTeX source file not found: '%s'") % src)
				rubber.util.abort_generic_error ()

			saved_vars = env.main.vars
			env.main.vars = rubber.util.Variables (saved_vars, { "cwd": initial_dir })
			for dir in self.path:
				env.main.do_path(dir)
			for cmd in self.prologue:
				cmd = rubber.util.parse_line (cmd, env.main.vars)
				env.main.command(cmd[0], cmd[1:], {'file': 'command line'})
			env.main.vars = saved_vars

			env.main.parse()

			saved_vars = env.main.vars
			env.main.vars = rubber.util.Variables (saved_vars, { "cwd": initial_dir })
			for cmd in self.epilogue:
				cmd = rubber.util.parse_line (cmd, env.main.vars)
				env.main.command(cmd[0], cmd[1:], {'file': 'command line'})
			env.main.vars = saved_vars

			if self.compress is not None:
				last_node = env.final
				filename = last_node.products[0]
				if self.compress == 'gzip':
					import gzip
					env.final = rubber.converters.compressor.Node (
						env.depends, gzip.GzipFile, '.gz', filename)
				else: # self.compress == 'bzip2'
					import bz2
					env.final = rubber.converters.compressor.Node (
						env.depends, bz2.BZ2File, '.bz2', filename)

			self.process_source (env)

		exit (0)

	def clean (self, env):
		"""
		Remove all products.
		This function should never throw or call exit
		"""
		for dep in env.final.set.values ():
			dep.clean ()

	def build (self, env):
		"""
		Build the final product.
		"""
		srcname = env.main.sources[0]
		# FIXME unindent, untangle
		if True:
			if self.force:
				ret = env.main.make(True)
				if ret != ERROR and env.final is not env.main:
					ret = env.final.make()
				else:
					# This is a hack for the call to get_errors() below
					# to work when compiling failed when using -f.
					env.final.failed_dep = env.main.failed_dep
			else:
				ret = env.final.make(self.force)

			if ret == ERROR:
				msg.info(_("There were errors compiling %s.") % srcname)
				number = self.max_errors
				for err in env.final.failed().get_errors():
					if number == 0:
						msg.info(_("More errors."))
						break
					msg.display(**err)
					number -= 1
				rubber.util.abort_generic_error ()

			if ret == UNCHANGED:
				msg(1, _("nothing to be done for %s") % srcname)

			if self.warn:
				# FIXME
				log = env.main.log
				if not env.main.parse_log ():
					msg.error(_("cannot read the log file"))
					return 1
				msg.display_all(log.parse(boxes=self.warn_boxes,
					refs=self.warn_refs, warnings=self.warn_misc))

	def __call__ (self, cmdline):
		"""
		This method is a wrapper around the main method,
		catching the keyboard interruption signal.
		"""
		try:
			self.main (cmdline)
			assert False
		except KeyboardInterrupt:
			msg(0, _("*** interrupted"))
			rubber.util.abort_generic_error ()

class Clean (Main):
	"""
	rubber --clean
	"""
	def __init__ (self):
		super (Clean, self).__init__ (mode="clean")

	def process_source (self, env):
		self.clean (env)

class Build (Main):
	"""
	plain rubber
	"""
	def __init__ (self):
		super (Build, self).__init__ (mode="build")

	def parse_opts (self, cmdline):
		self.force = False
		return super (Build, self).parse_opts (cmdline)

	def process_source (self, env):
		self.build (env)

class Pipe (Main):
	def __init__ (self):
		super (Pipe, self).__init__ (mode="pipe")
		# FIXME why?
		msg.level = 0

	def help (self):
		sys.stderr.write (_("""\
This is Rubber version %s.
usage: rubber-pipe [options]
available options:
  -b, --bzip2              compress the final document with bzip2
  -c, --command=CMD        run the directive CMD before parsing (see man page)
  -e, --epilogue=CMD       run the directive CMD after parsing
  -z, --gzip               compress the final document
  -h, --help               display this help
      --into=DIR           go to directory DIR before compiling
  -k, --keep               keep the temporary files after compiling
  -l, --landscape          change paper orientation (if relevant)
  -n, --maxerr=NUM         display at most NUM errors (default: 10)
  -m, --module=MOD[:OPTS]  use module MOD (with options OPTS)
      --only=SOURCES       only include the specified SOURCES
  -o, --post=MOD[:OPTS]    postprocess with module MOD (with options OPTS)
  -d, --pdf                produce a pdf (synonym for -m pdftex or -o ps2pdf)
  -p, --ps                 process through dvips (synonym for -m dvips)
  -q, --quiet              suppress messages
  -r, --read=FILE          read additional directives from FILE
  -S, --src-specials       enable insertion of source specials
  -s, --short              display errors in a compact form
  -I, --texpath=DIR        add DIR to the search path for LaTeX
  -v, --verbose            increase verbosity
      --version            print version information and exit
""") % rubber_version)

	def short_help (self):
		# normally, Rubber prints a short help text if no arguments
		# at all are given.  This is valid for rubber-pipe, though.
		pass

	def parse_opts (self, cmdline):
		self.keep_temp = False
		args = super (Pipe, self).parse_opts (cmdline)
		# rubber-pipe doesn't take file arguments
		for arg in args:
			self.ignored_option (arg)
		# --inplace nonsensical since we don't have a filename
		if self.place is None:
			self.illegal_option ("--inplace")
		# hack: force is required by self.build
		self.force = False
		return [ "-" ]   # this will be stdin

	def prepare_source (self, filename):
		"""
		Dump the standard input in a file, and set up that file
		the same way we would normally process LaTeX sources.
		"""
		assert filename.endswith ("-")  # filename is ignored

		try:
			# Make a temporary on-disk copy of the standard input,
			# in the current working directory.
			# The name will have the form "rubtmpXXX.tex.
			with tempfile.NamedTemporaryFile (suffix='.tex', prefix='rubtmp', dir='.', delete=False) as srcfile:
				# note the tempfile name so we can remove it later
				self.pipe_tempfile = srcfile.name
				# copy stdin into the tempfile
				msg.progress (_("saving the input in %s") % self.pipe_tempfile)
				shutil.copyfileobj (sys.stdin, srcfile)
		except IOError:
			msg.error (_("cannot create temporary file for the main LaTeX source"))
			rubber.util.abort_generic_error ()

		return super (Pipe, self).prepare_source (self.pipe_tempfile)

	def process_source (self, env):
		"""
		Build the document, and dump the result on stdout.
		"""
		try:
			self.build (env)
			filename = env.final.products[0]
			try:
				# dump the results on standard output
				with open (filename, "r") as output:
					shutil.copyfileobj (output, sys.stdout)
			except IOError:
				msg.error (_("error copying the product '%s' to stdout") % filename)
				rubber.util.abort_generic_error ()
		finally:
			# clean the intermediate files
			if not self.keep_temp:
				self.clean (env)
				rubber.util.verbose_remove (self.pipe_tempfile)

class Info (Main):
	def __init__ (self):
		super (Info, self).__init__ (mode="info")
		# FIXME why?
		self.max_errors = -1
		# FIXME why?
		msg.write = rubber.util.stdout_write

	def short_help (self):
		sys.stderr.write (_("""\
usage: rubber-info [options] source
For more information, try `rubber-info --help'.
"""))
		rubber.util.abort_rubber_syntax_error ()

	def help (self):
		sys.stderr.write (_("""\
This is Rubber's information extractor version %s.
usage: rubber-info [options] source
available options:
  all options accepted by rubber(1)
actions:
  --boxes     report overfull and underfull boxes
  --check     report errors or warnings (default action)
  --deps      show the target file's dependencies
  --errors    show all errors that occured during compilation
  --help      display this help
  --refs      show the list of undefined references
  --rules     print the dependency rules including intermediate results
  --version   print the program's version and exit
  --warnings  show all LaTeX warnings
""") % rubber_version)

	def parse_opts (self, cmdline):
		self.info_action = None
		ret = super (Info, self).parse_opts (cmdline)
		if self.info_action is None:
			self.info_action = "check"
		return ret

	# FIXME rewrite
	def process_source (self, env):
		if self.info_action == "deps":
			from rubber.depend import Leaf
			deps = [ k for k,n in env.depends.iteritems () if type (n) is Leaf ]
			rubber.util.stdout_write (string.join (deps))

		elif self.info_action == "rules":
			seen = {}
			next = [self.env.final]
			while len(next) > 0:
				node = next[0]
				next = next[1:]
				if seen.has_key(node):
					continue
				seen[node] = None
				if len(node.sources) == 0:
					continue
				print ("\n%s:" % string.join(node.products))
				print (string.join(node.sources))
				next.extend(node.source_nodes())
		else:
			self.info_log (self.info_action)

	# FIXME rewrite
	def info_log (self, act):
		"""
		Check for a log file and extract information from it if it exists,
		accroding to the argument's value.
		"""
		log = self.env.main.log
		if not self.env.main.parse_log ():
			msg.error(_("Parsing the log file failed"))
			rubber.util.abort_generic_error ()

		if act == "boxes":
			if not msg.display_all(log.get_boxes()):
				msg.info(_("There is no bad box."))
		elif act == "check":
			if msg.display_all(log.get_errors()): return 0
			msg.info(_("There was no error."))
			if msg.display_all(log.get_references()): return 0
			msg.info(_("There is no undefined reference."))
			if not msg.display_all(log.get_warnings()):
				msg.info(_("There is no warning."))
			if not msg.display_all(log.get_boxes()):
				msg.info(_("There is no bad box."))
		elif act == "errors":
			if not msg.display_all(log.get_errors()):
				msg.info(_("There was no error."))
		elif act == "refs":
			if not msg.display_all(log.get_references()):
				msg.info(_("There is no undefined reference."))
		elif act == "warnings":
			if not msg.display_all(log.get_warnings()):
				msg.info(_("There is no warning."))
		else:
			sys.stderr.write(_("\
I don't know the action `%s'. This should not happen.\n") % act)
			return 1
		return 0
