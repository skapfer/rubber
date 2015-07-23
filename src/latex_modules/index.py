# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2004--2006
# vim: noet:ts=4
"""
Indexing support with package 'index'.

This module handles the processing of the document's indices using a tool like
makeindex or xindy. It stores an MD5 sum of the source (.idx) file between two
runs, in order to detect modifications.

The following directives are provided to specify options for makeindex:

  tool <tool> =
    Choose which indexing tool should be used. Currently this can be either
	"makeindex" (by default) or "xindy".

  language <lang> =
    Choose the language used for sorting the index (xindy only).

  modules <mod> <mod> ... =
  	Specify which modules xindy should use for the index.

  order <ordering> =
    Modify the ordering to be used (makeindex only, supported by xindy with
	warnings). The argument must be a space separated list of:
    - standard = use default ordering (no options, this is the default)
    - german = use German ordering (option "-g")
    - letter = use letter instead of word ordering (option "-l")

  path <directory> =
    Add the specified directory to the search path for styles.

  style <name> =
    Use the specified style file.

They all accept an optional argument first, enclosed in parentheses as in
"index.path (foo,bar) here/", to specify which index they apply to. Without
this argument, they apply to all indices declared at the point where they
occur.
"""

import re

from rubber.index import Index
from rubber.util import _, msg

re_optarg = re.compile(r'\((?P<list>[^()]*)\) *')

def setup (document, context):
	global doc, indices, defaults, commands
	doc = document
	indices = {}
	defaults = []
	commands = {}
	doc.hook_macro('makeindex', '', hook_makeindex)
	doc.hook_macro('newindex', 'aaa', hook_newindex)

def register (name, idx, ind, ilg):
	"""
	Register a new index.
	"""
	index = indices[name] = Index(doc, idx, ind, ilg)
	for command in defaults:
		index.command(*command)
	if name in commands:
		for command in commands[name]:
			index.command(*command)

def hook_makeindex (loc):
	register('default', 'idx', 'ind', 'ilg')

def hook_newindex (loc, index, idx, ind):
	register(index, idx, ind, 'ilg')
	msg.log(_("index %s registered") % index, pkg='index')

def command (cmd, args):
	names = None

	# Check if there is the optional argument.

	if len(args) > 0:
		match = re_optarg.match(args[0])
		if match:
			names = match.group('list').split(',')
			args = args[1:]

	# If not, this command will also be executed for newly created indices
	# later on.

	if names is None:
		defaults.append([cmd, args])
		names = indices.keys()

	# Then run the command for each index it concerns.

	for name in names:
		if name in indices:
			indices[name].command(cmd, args)
		elif name in commands:
			commands[name].append([cmd, args])
		else:
			commands[name] = [[cmd, args]]
