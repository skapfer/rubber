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

def setup (doc, context):
	# overwrite the hook which would load the bibtex module
	doc.hook_macro ("bibliographystyle", "a", hook_bibliographystyle)

	opt = context["opt"] or None
	options = rubber.util.parse_keyval(opt) if opt != None else {}

	if "backend" in options and options["backend"] != "biber":
		rubber.biblio.setup (doc, "bibtex")
	else:
		rubber.biblio.setup (doc, "biber")

def hook_bibliographystyle (loc, bibs):
	msg.warn (_("\\usepackage{biblatex} incompatible with \\bibliographystyle"), pkg="biblatex")
