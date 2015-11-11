# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# (c) Sebastian Kapfer, 2015
# vim: noet:ts=4
"""
This is the command line interface for the information extractor.
"""

import sys
import string

from rubber.util import _, msg
import rubber.cmdline
import rubber.util
import rubber.version

class Info (rubber.cmdline.Main):
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
		sys.exit (1)

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
""") % rubber.version.version)

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
			exit (2)

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
