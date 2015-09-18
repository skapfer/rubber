# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# vim: noet:ts=4
"""
Support for the `graphics' package in Rubber.

This package is destined de become something rather large, to support standard
schemes for generating the figures that are supposed to be included, among
other features.

Another feature to include in the future concerns the parsing of the commands
that customize the operation of the package, such as \\DeclareGraphicsRule.

Currently, only dependency analysis is provided. The command parsing is
incomplete, because \\includegraphics can have a complex format.
"""

import os, os.path
import string, re

from rubber import _, msg
from rubber.util import parse_keyval
from rubber.tex import parse_string
import rubber.module_interface

# default suffixes for each device driver (taken from the .def files)

# For dvips and dvipdf we put the suffixes .bb instead of .gz because these
# are the files LaTeX actually looks for. The module `eps_gz' declares the
# gzipped files as dependencies for them and extracts the bounding box
# information.

drv_suffixes = {
	"dvipdf" : ["", ".eps", ".ps", ".eps.bb", ".ps.bb", ".eps.Z"],
	"dvipdfm" : ["", ".jpg", ".jpeg", ".pdf", ".png"],
	"dvips" : ["", ".eps", ".ps", ".eps.bb", ".ps.bb", ".eps.Z"],
	"dvipsone" : ["", ".eps", ".ps", ".pcx", ".bmp"],
	"dviwin" : ["", ".eps", ".ps", ".wmf", ".tif"],
	"emtex" : ["", ".eps", ".ps", ".pcx", ".bmp"],
	"pctex32" : ["", ".eps", ".ps", ".wmf", ".bmp"],
	"pctexhp" : ["", ".pcl"],
	"pctexps" : ["", ".eps", ".ps"],
	"pctexwin" : ["", ".eps", ".ps", ".wmf", ".bmp"],
	"pdftex" : ["", ".png", ".pdf", ".jpg", ".mps", ".tif"],
	"tcidvi" : [""],
	"textures" : ["", ".ps", ".eps", ".pict"],
	"truetex" : ["", ".eps", ".ps"],
	"vtex" : ["", ".gif", ".png", ".jpg", ".tif", ".bmp", ".tga", ".pcx",
	          ".eps", ".ps", ".mps", ".emf", ".wmf"]
}

class Module (rubber.module_interface.Module):

    def __init__ (self, document, context):
        self.doc = document
        document.hook_macro ('includegraphics', '*oa', self.hook_includegraphics)
        document.hook_macro ('graphicspath', 'a', self.hook_graphicspath)
        document.hook_macro ('DeclareGraphicsExtensions', 'a', self.hook_declareExtensions)
        document.hook_macro ('DeclareGraphicsRule', 'aaaa', self.hook_declareRule)

        self.prefixes = [os.path.join(x, '') for x in document.env.path]
        self.files = []

        # I take dvips as the default, but it is not portable.

        if document.vars['engine'] == 'pdfTeX' and document.products[0][-4:] == '.pdf':
            self.suffixes = drv_suffixes['pdftex']
        elif document.vars['engine'] == 'VTeX':
            self.suffixes = drv_suffixes['vtex']
        else:
            self.suffixes = drv_suffixes['dvips']

        # If the package was loaded with an option that matches the name of a
        # driver, use that driver instead.

        opts = parse_keyval(context['opt'])

        for opt in opts.keys():
            if drv_suffixes.has_key(opt):
                self.suffixes = drv_suffixes[opt]

        document.vars['graphics_suffixes'] = self.suffixes

    # Supported macros

    def hook_includegraphics (self, loc, starred, optional, name):
        # no suffixes are tried when the extension is explicit

        allowed_suffixes = self.suffixes

        options = parse_keyval(optional)
        if 'ext' in options:
             allowed_suffixes = ['']
             if options['ext']:
                 name = name + options['ext']

        for suffix in self.suffixes:
            if name[-len(suffix):] == suffix:
                allowed_suffixes = ['']
                break

        # If the file name looks like it contains a control sequence or a macro
        # argument, forget about this \includegraphics.

        if name.find('\\') >= 0 or name.find('#') >= 0:
            return

        # We only accept conversions from file types we don't know and cannot
        # produce.

        def check (vars):
            source = vars['source']
            if os.path.exists(vars['target']) and self.doc.env.may_produce(source):
                return False
            if self.suffixes == ['']:
                return True
            for suffix in allowed_suffixes:
                if source[-len(suffix):] == suffix:
                    return False
            return True

        node = self.doc.env.convert (name, suffixes=allowed_suffixes,
                                     prefixes=self.prefixes,
                                     check=check, context=self.doc.vars)

        if node:
            msg.log(_("graphics `%s' found") % name, pkg='graphics')
            for file in node.products:
                self.doc.add_source(file)
            self.files.append(node)
        else:
            msg.warn(_("graphics `%s' not found") % name, **dict(loc))

    def hook_graphicspath (self, loc, arg):
        # The argument of \graphicspath is a list (in the sense of TeX) of
        # prefixes that can be put in front of graphics names.
        parser = parse_string(arg)
        while True:
            arg = parser.get_argument_text()
            if arg is None:
                break
            self.prefixes.insert(0, arg)

    def hook_declareExtensions (self, loc, list):
        for suffix in list.split(","):
            self.suffixes.insert(0, string.strip(suffix))

    def hook_declareRule (self, loc, ext, type, read, command):
        if read in self.suffixes:
            return
        self.suffixes.insert(0, read)
        msg.log("*** FIXME ***  rule %s -> %s [%s]" % (string.strip (ext), read, type), pkg='graphics')

    #  module interface

    def pre_compile (self):
        # Pre-compilation means running all needed conversions. This is not done
        # through the standard dependency mechanism because we do not want to
        # interrupt compilation when a graphic is not found.
        for node in self.files:
            if not node.making:
                node.make()
            else:
                msg.log("*** FIXME ***  recursive making in graphics: %s" % str (node.products), pkg="graphics")
        return True

    def clean (self):
        for node in self.files:
            node.clean()
