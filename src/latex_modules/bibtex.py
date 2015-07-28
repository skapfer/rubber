# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# vim: noet:ts=4
"""
BibTeX support for Rubber

This module is a special one: it is triggered by the macros \\bibliography and
\\bibliographystyle and not as a package, so the main system knows about it.
The module provides the following commands:

  path <dir> = adds <dir> to the search path for databases
  stylepath <dir> = adds <dir> to the search path for styles
"""

from rubber.biblio import Bibliography

def setup (doc, context):
	global biblio
	biblio = Bibliography (doc)
	doc.hook_macro('bibliography', 'a', biblio.hook_bibliography)
	doc.hook_macro('bibliographystyle', 'a', biblio.hook_bibliographystyle)
def command (command, args):
	getattr(biblio, 'do_' + command)(*args)
def pre_compile ():
	return biblio.pre_compile()
def get_errors ():
	return biblio.get_errors()
def clean ():
	biblio.clean()
