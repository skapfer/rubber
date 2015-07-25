# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2003--2006
"""
Support for package 'combine' in Rubber.

This package is used to gather several complete LaTeX documents into a single
one, possibly fine-tuning page numbering, generation of tables of contents,
and other features. Documents are included using the macro \\import, so
basically this support module makes it behave somewhat like \\include.
However, more subtle behaviour could be implemented, e.g. to reflect the the
way the package deals with \\documentclass and \\usepackage.
"""

from os.path import basename
from rubber.converters.latex import EndDocument
import rubber.module_interface

# FIXME: should add the appropriate dependency nodes for the new .aux
# .log .tex files, or a new LatexDep node, or ..?

class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        self.doc = document
        self.combine_level = 0
        document.hook_begin('document', self.begin)
        document.hook_end('document', self.end)
        document.hook_macro('import', 'a', self.import_doc)

    def begin (self, loc):
        self.combine_level += 1

    def end (self, loc):
        if self.combine_level == 1:
            raise EndDocument
        self.combine_level -= 1

    def import_doc (self, loc, name):
        file, _ = self.doc.input_file(name + '.tex')
        if file:
            return
        base = basename(file[:-4])

        # Here we should temporarily change the base name instead of
        # forcefully remove .toc and similar files.

        self.doc.removed_files.extend(
            [base + '.aux', base + '.toc', base + '.lof', base + '.lot'])
