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

	options = rubber.util.parse_keyval (context ["opt"])
	try:
		backend = options ["backend"]
	except KeyError:
		backend = "biber"
	if backend == "biber":
		rubber.biblio.Biber (doc.set, doc)
	else:
		assert backend in ("bibtex", "bibtex8", "bibtexu")
		rubber.biblio.BibTeX (doc.set, doc)

def hook_bibliographystyle (loc, bibs):
	msg.warn (_("\\usepackage{biblatex} incompatible with \\bibliographystyle"), pkg="biblatex")
