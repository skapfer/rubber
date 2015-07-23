# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006

from rubber.index import Index

def setup (document, context):
	global index
	index = Index(document, 'idx', 'ind', 'ilg')

def command (command, args):
	getattr(index, 'do_' + command)(*args)
