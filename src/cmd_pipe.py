# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2003--2006
# (c) Sebastian Kapfer, 2015
# vim: noet:ts=4
"""
This is the command line pipe interface for Rubber.
"""

import os
import sys
import re

import rubber.cmdline
from rubber.util import _, msg
import rubber.version

re_rubtmp = re.compile("rubtmp(?P<num>[0-9]+)\\.")

def make_name ():
	"""
	Return a base name suitable for a new compilation in the current
	directory. The name will have the form "rubtmp" plus a number, such
	that no file of this prefix exists.
	"""
	num = 0
	for file in os.listdir("."):
		m = re_rubtmp.match(file)
		if m:
			num = max(num, int(m.group("num")) + 1)
	return "rubtmp%d" % num

def dump_file (f_in, f_out):
	"""
	Dump the contents of a file object into another.
	"""
	for line in f_in.readlines():
		f_out.write(line)

class Pipe (rubber.cmdline.Main):
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
""") % rubber.version.version)

	def short_help (self):
		# normally, Rubber prints a short help text if no arguments
		# at all are given.  This is valid for rubber-pipe, though.
		pass

	def parse_opts (self, cmdline):
		args = super (Pipe, self).parse_opts (cmdline)
		self.keep_temp = False
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
			filename = make_name () + ".tex"
			# note the tempfile name so we can remove it later
			self.pipe_tempfile = filename
			# copy stdin into the tempfile
			srcfile = open (filename, "w")
			msg.progress (_("saving the input in %s") % filename)
			dump_file (sys.stdin, srcfile)
			srcfile.close ()
		except IOError:
			msg.error (_("cannot create temporary file '%s'") % filename)
			sys.exit (2)

		return super (Pipe, self).prepare_source (filename)

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
					dump_file (output, sys.stdout)
			except IOError:
				msg.error (_("error copying the product '%s' to stdout") % filename)
				sys.exit (2)
		finally:
			# clean the intermediate files
			if not self.keep_temp:
				self.clean (env)
				rubber.util.verbose_remove (self.pipe_tempfile)
