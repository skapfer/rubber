# vim: noet:ts=4
# This file is part of Rubber and thus covered by the GPL
# Sebastian Kapfer <sebastian.kapfer@fau.de> 2015.
# based on code by Sebastian Reichel and others.
"""
BibLaTeX support for Rubber
"""

from rubber.util import _, msg
import rubber.util
import rubber.biblio
import sys
import rubber.module_interface

class Module (rubber.module_interface.Module):
    def __init__ (self, document, context):
        # overwrite the hook which would load the bibtex module
        document.hook_macro ("bibliographystyle", "a", hook_bibliographystyle)

        options = rubber.util.parse_keyval (context ["opt"])
        backend = options.setdefault ("backend", "biber")

        if backend not in ("biber", "bibtex", "bibtex8", "bibtexu"):
            msg.error (_("Garbled biblatex backend: backend=%s (aborting)") % backend)
            sys.exit (1)  # abort rather than guess
        if backend == "biber":
            rubber.biblio.Biber (document.set, document)
        else:
            rubber.biblio.BibTeX (document.set, document, tool=backend)

def hook_bibliographystyle (loc, bibs):
    msg.warn (_("\\usepackage{biblatex} incompatible with \\bibliographystyle"), pkg="biblatex")
