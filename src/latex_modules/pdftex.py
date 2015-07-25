# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# vim: noet:ts=4
"""
pdfLaTeX support for Rubber.

When this module is loaded with the otion 'dvi', the document is compiled to
DVI using pdfTeX.
"""

from rubber import _, msg
import rubber.module_interface

class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        self.doc = document
        self.mode = None
        document.vars['program'] = 'pdflatex'
        document.vars['engine'] = 'pdfTeX'
        try:
            opt = context['opt']
        except KeyError:
            opt = None
        if opt == 'dvi':
            self.mode_dvi()
        else:
            self.mode_pdf()

    def mode_pdf (self):
        if self.mode == 'pdf':
            return
        if self.doc.env.final != self.doc and self.doc.products[0][-4:] != '.pdf':
            msg.error(_("there is already a post-processor registered"))
            return
        self.doc.set_primary_product_suffix (".pdf")
        self.doc.cmdline = [
            opt for opt in self.doc.cmdline if opt != '\\pdfoutput=0']
        self.mode = 'pdf'

    def mode_dvi (self):
        if self.mode == 'dvi':
            return
        if self.doc.env.final != self.doc and self.doc.products[0][-4:] != '.dvi':
            msg.error(_("there is already a post-processor registered"))
            return
        self.doc.set_primary_product_suffix (".dvi")
        self.doc.cmdline.insert(0, '\\pdfoutput=0')
        self.mode = 'dvi'
