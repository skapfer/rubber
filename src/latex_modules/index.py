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
import rubber.module_interface

re_optarg = re.compile(r'\((?P<list>[^()]*)\) *')

class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        self.doc = document
        self.indices = {}
        self.defaults = []
        self.commands = {}
        document.hook_macro('makeindex', '', self.hook_makeindex)
        document.hook_macro('newindex', 'aaa', self.hook_newindex)

    def register (self, name, idx, ind, ilg):
        """
        Register a new index.
        """
        index = self.indices[name] = Index(self.doc, idx, ind, ilg)
        for command in self.defaults:
            index.command(*command)
        if name in self.commands:
            for command in self.commands [name]:
                index.command(*command)

    def hook_makeindex (self, loc):
        self.register('default', 'idx', 'ind', 'ilg')

    def hook_newindex (self, loc, index, idx, ind):
        self.register(index, idx, ind, 'ilg')
        msg.log(_("index %s registered") % index, pkg='index')
    def command (self, cmd, args):
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
            self.defaults.append([cmd, args])
            names = self.indices.keys()

        # Then run the command for each index it concerns.

        for name in names:
            if name in self.indices:
                self.indices[name].command(cmd, args)
            elif name in self.commands:
                self.commands[name].append([cmd, args])
            else:
                self.commands[name] = [[cmd, args]]
