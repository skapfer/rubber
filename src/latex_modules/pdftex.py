# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# vim: noet:ts=4
"""
pdfLaTeX support for Rubber.

When this module is loaded with the otion 'dvi', the document is compiled to
DVI using pdfTeX.
"""

from rubber import _, msg

def setup (document, context):
	global doc, mode
	doc = document
	mode = None
	doc.vars['program'] = 'pdflatex'
	doc.vars['engine'] = 'pdfTeX'
	try:
		opt = context['opt']
	except KeyError:
		opt = None
	if opt == 'dvi':
		mode_dvi()
	else:
		mode_pdf()

def mode_pdf ():
	global mode
	if mode == 'pdf':
		return
	if doc.env.final != doc and doc.products[0][-4:] != '.pdf':
		msg.error(_("there is already a post-processor registered"))
		return
	doc.set_primary_product_suffix (".pdf")
	doc.cmdline = [
		opt for opt in doc.cmdline if opt != '\\pdfoutput=0']
	mode = 'pdf'

def mode_dvi ():
	global mode
	if mode == 'dvi':
		return
	if doc.env.final != doc and doc.products[0][-4:] != '.dvi':
		msg.error(_("there is already a post-processor registered"))
		return
	doc.set_primary_product_suffix (".dvi")
	doc.cmdline.insert(0, '\\pdfoutput=0')
	mode = 'dvi'
