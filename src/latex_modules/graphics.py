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
import re
import logging
msg = logging.getLogger (__name__)
import rubber.depend
from rubber.util import _
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

    def __init__ (self, document, opt):
        self.doc = document
        document.hook_macro ('includegraphics', '*oa', self.hook_includegraphics)
        document.hook_macro ('graphicspath', 'a', self.hook_graphicspath)
        document.hook_macro ('DeclareGraphicsExtensions', 'a', self.hook_declareExtensions)
        document.hook_macro ('DeclareGraphicsRule', 'aaaa', self.hook_declareRule)

        self.prefixes = [os.path.join(x, '') for x in document.env.path]
        self.files = []

        #Latex accepts upper and lowercase filename extensions
        # to keep the above lists clean we auto-generate the
        # uppercase versions of the extensions automatically
        for engine,suffixes in drv_suffixes.items():
            suffixes += [x.upper() for x in suffixes]

        # I take dvips as the default, but it is not portable.
        if document.engine == 'pdfTeX' \
           and document.primary_product ().endswith ('.pdf'):
            self.suffixes = drv_suffixes['pdftex']
        elif document.engine == 'VTeX':
            self.suffixes = drv_suffixes['vtex']
        else:
            self.suffixes = drv_suffixes['dvips']

        # If the package was loaded with an option that matches the name of a
        # driver, use that driver instead.

        opts = parse_keyval (opt)

        for opt in opts.keys():
            if opt in drv_suffixes:
                self.suffixes = drv_suffixes[opt]

        document.env.graphics_suffixes = self.suffixes

    # Supported macros

    def hook_includegraphics (self, loc, starred, optional, name):
        # no suffixes are tried when the extension is explicit

        options = parse_keyval(optional)
        allowed_suffixes = self.suffixes

        # work out the file extension if given explicitly
        if 'ext' in options and options['ext']:
            # \includegraphics[ext=.png]{foo} and \includegraphics[ext=.png]{{{foo}}}
            allowed_suffixes = ['']
            if name.startswith ('{{') and name.endswith ('}}'):
                name = name [2:-2]
            name = name + options['ext']
        elif name.startswith ('{{') and name.endswith ('}}'):
            # \includegraphics{{{foo}}}
            name = name [2:-2]
        else:
            for suffix in self.suffixes:
                # if extension is given, includegraphics will always search for that
                # and disable automatic discovery
                if suffix and name.endswith (suffix):
                    allowed_suffixes = ['']
                    # support special syntax \includegraphics{subdir/{foo.1}.png}
                    # at least some of the time
                    if name.endswith ('}' + suffix):
                        # try to emulate what the TeX parser does.
                        name = re.sub('{([^{]*)}', '\\1', name)
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

        if isinstance (node, str):
            msg.debug (_("graphics %s found in %s"), name, node)
            self.doc.add_source (node)
        elif isinstance (node, rubber.depend.Node):
            msg.debug (_("graphics %s converted from %s"),
                       name, node.primary_product ())
            self.doc.add_source (node.primary_product ())
            self.files.append(node)
        else:
            assert node is None
            msg.warning (rubber.util._format (loc, _("graphics `%s' not found") % name))

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
            self.suffixes.insert(0, suffix.strip())

    def hook_declareRule (self, loc, ext, type, read, command):
        if read in self.suffixes:
            return
        self.suffixes.insert(0, read)
        msg.debug("*** FIXME ***  rule %s -> %s [%s]" % (ext.strip (), read, type))

    #  module interface

    def pre_compile (self):
        # Pre-compilation means running all needed conversions. This is not done
        # through the standard dependency mechanism because we do not want to
        # interrupt compilation when a graphic is not found.
        for node in self.files:
            assert not node.making
            node.make ()
        return True
