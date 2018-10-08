# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# vim: noet:ts=4
"""
pdfLaTeX support for Rubber.

When this module is loaded with the otion 'dvi', the document is compiled to
DVI using pdfTeX.
"""

import rubber.module_interface

class Module (rubber.module_interface.Module):
    def __init__ (self, document, opt):
        self.doc = document
        self.mode = None
        document.program = 'pdflatex'
        document.engine = 'pdfTeX'
        if opt == 'dvi':
            self.mode_dvi()
        else:
            self.mode_pdf()

    def mode_pdf (self):
        if self.mode == 'pdf':
            return
        self.doc.register_post_processor (old_suffix='.pdf', new_suffix='.pdf')
        self.doc.cmdline = [
            opt for opt in self.doc.cmdline if opt != '\\pdfoutput=0']
        self.mode = 'pdf'

    def mode_dvi (self):
        if self.mode == 'dvi':
            return
        self.doc.register_post_processor (old_suffix='.dvi', new_suffix='.dvi')
        self.doc.cmdline.insert(0, '\\pdfoutput=0')
        self.mode = 'dvi'
