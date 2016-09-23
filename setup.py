#!/usr/bin/env python2
# vim: et:ts=4
#
# This is the setup script for Rubber. It acts both as a part of the
# configuration script a la autoconf and as a setup script a la Distutils.
#
# As the rest of Rubber, this script is covered by the GPL (see COPYING).
# Copyright 2002-2006 Emmanuel Beffara
# Copyright 2015-2015 Sebastian Kapfer
# Copyright 2015-2015 Nicolas Boulenguez

import distutils.cmd
import distutils.command.build
import distutils.command.clean
import distutils.command.install
import distutils.core
import distutils.dir_util
import distutils.log
import distutils.util
import os.path
import re

# A file f is generated from f.in by replacing @author@, @version@ by
# sensible values (as ./configure does in the autoconf world).
files_with_substitutions = (
    os.path.join ("doc", "man-en", "rubber.1"),
    os.path.join ("doc", "man-en", "rubber-info.1"),
    os.path.join ("doc", "man-fr", "rubber.1"),
    os.path.join ("doc", "man-fr", "rubber-info.1"),
    os.path.join ("doc", "rubber.texi"),
    os.path.join ("src", "version.py"),
)

manual_basename = os.path.join ("doc", "rubber.")
doc_recipes = (
    ("html", ("makeinfo", "--html", "--no-split")),
    ("info", ("makeinfo", "--info")),
    ("pdf",  ("texi2dvi", "--pdf", "--quiet", "--tidy")),
    ("txt",  ("makeinfo", "--plaintext")),
)

class build (distutils.command.build.build):
    man  = True
    info = True
    html = True
    pdf  = True
    txt  = False
    user_options = distutils.command.build.build.user_options + [
        ("man=",  None, "build Manpages [{}]".format (man)),
        ("info=", None, "build Info documentation [{}]".format (info)),
        ("html=", None, "format HTML documentation [{}]".format (html)),
        ("pdf=",  None, "format PDF documentation [{}]".format (pdf)),
        ("txt=",  None, "format plain text documentation [{}]".format (txt)),
    ]

    def finalize_options (self):
        distutils.command.build.build.finalize_options (self)
        for fmt in [ 'man' ] + [ fmt for fmt, recipe in doc_recipes ]:
            value = getattr (self, fmt)
            if type (value) is str:
                value = distutils.util.strtobool (value)
                setattr (self, fmt, value)

    def generate_files_with_substitutions (self, subs):
        pattern = "|".join (subs.keys ())
        pattern = "@(" + pattern + ")@"
        pattern = re.compile (pattern)
        def repl (match_object):
            return subs [match_object.group (1)]
        def func (in_path, out_path):
            with open (in_path) as in_file:
                with open (out_path, "w") as out_file:
                    for in_line in in_file:
                        out_line = pattern.sub (repl, in_line)
                        out_file.write (out_line)
        for out_path in files_with_substitutions:
            if re.match ('.*man-??.*\\.1', out_path) and not self.man:
                continue
            in_path = out_path + ".in"
            self.make_file (in_path, out_path, func, (in_path, out_path))

    def generate_documentation (self):
        infile = manual_basename + "texi"
        for fmt, recipe in doc_recipes:
            if getattr (self, fmt):
                outfile = manual_basename + fmt
                cmd = recipe + ("--output=" + outfile, infile)
                self.make_file (infile, outfile, self.spawn, (cmd, ))

    def run (self):
        subs = {}
        for v in ("author", "author_email", "url", "version"):
            subs [v] = getattr (self.distribution.metadata, "get_"+v) ()
        self.generate_files_with_substitutions (subs)

        distutils.command.build.build.run (self)

        self.generate_documentation ()

class install (distutils.command.install.install):

    mandir  = "$base/man"
    infodir = "$base/info"
    docdir  = "$base/share/doc/rubber"
    user_options = distutils.command.install.install.user_options + [
        ("mandir=", None, "installation directory for manual pages [{}]".format (mandir)),
        ("infodir=", None, "installation directory for info manuals [{}]".format (infodir)),
        ("docdir=", None, "installation directory for other documentation [{}]".format (docdir)),
    ]

    def finalize_options (self):
        distutils.command.install.install.finalize_options (self)
        self._expand_attrs (("mandir", "infodir", "docdir"))

    def run (self):
        build = self.get_finalized_command ("build")
        assert self.distribution.data_files == None
        self.distribution.data_files = []
        if build.man:
            self.distribution.data_files = [
                (self.mandir + "/man1", (
                    "doc/man-en/rubber.1",
                    "doc/man-en/rubber-info.1",
                    "doc/man-en/rubber-pipe.1",
                )),
                (self.mandir + "/fr/man1", (
                    "doc/man-fr/rubber.1",
                    "doc/man-fr/rubber-info.1",
                    "doc/man-fr/rubber-pipe.1",
                ))
            ]
        if build.info:
            infodocs = (manual_basename + "info", )
            self.distribution.data_files.append ((self.infodir, infodocs))
        otherdocs = [manual_basename + f for f in ("html", "pdf", "txt")
                     if getattr (build, f)]
        if len (otherdocs) > 0:
            self.distribution.data_files.append ((self.docdir, otherdocs))
        distutils.command.install.install.run (self)

class clean (distutils.command.clean.clean):

    def remove_tree (self, path):
        if os.path.exists (path):
            distutils.dir_util.remove_tree (path, dry_run=self.dry_run)
        else:
            distutils.log.debug ("'%s' does not exist -- can't clean it", path)

    def remove_file (self, path):
        if os.path.exists (path):
            distutils.log.info ("removing '%s'", path)
            if not self.dry_run:
                os.remove (path)

    def run (self):
        distutils.command.clean.clean.run (self)

        if self.all:
            for f in files_with_substitutions:
                self.remove_file (f)

        for fmt, _ in doc_recipes:
            self.remove_file (manual_basename + fmt)
        self.remove_tree ("rubber.t2d")

        for dirpath, dirnames, filenames in os.walk (os.curdir):
            for filename in filenames:
                ew = filename.endswith
                if ew ("~") or ew (".pyc") or ew (".pyo"):
                    self.remove_file (os.path.join (dirpath, filename))

        self.remove_tree (os.path.join ("tests", "tmp"))

class tar (distutils.cmd.Command):
    description = "wrapper for git archive"
    user_options = [
        ("revision=",  None, "git tree-ish [HEAD]"),
        ("extension=", None, "archive extension [tar.gz]"),
    ]
    revision  = "HEAD"
    extension = "tar.gz"
    def initialize_options (self):
        pass
    def finalize_options (self):
        pass
    def run (self):
        version = self.distribution.metadata.get_version ()
        self.spawn (("git", "archive", self.revision, "-9",
                     "--prefix=rubber-" + version + "/",
                     "--output=rubber-" + version + "." + self.extension))

def extract_version_from_first_line (news, pattern):
    with open (news, "r") as f:
        line = f.readline ()
    match = re.match (pattern, line)
    assert match, "Line 1 of " + news + " does not match '" + pattern + "'."
    return match.group (1)

distutils.core.setup (
    name = "rubber",
    version = extract_version_from_first_line ("NEWS", r'^Version ([0-9.]+) '),
    description = "an automated system for building LaTeX documents",
    long_description = """\
This is a building system for LaTeX documents. It is based on a routine that
runs just as many compilations as necessary. The module system provides a
great flexibility that virtually allows support for any package with no user
intervention, as well as pre- and post-processing of the document. The
standard modules currently provide support for bibtex, dvips, dvipdfm, pdftex,
makeindex. A good number of standard packages are supported, including
graphics/graphicx (with automatic conversion between various formats and
Metapost compilation).\
""",
    author = 'Sebastian Kapfer',
    author_email = 'sebastian.kapfer@fau.de',
    url = 'https://launchpad.net/rubber/',
    license = "GPL",
    packages = (
        "rubber",
        "rubber.converters",
        "rubber.latex_modules",
    ),
    package_dir = {
        "rubber" : "src",
    },
    package_data = {
        "rubber" : [ "latex_modules/*.rub", "rules.ini" ],
    },
    scripts = (
        "rubber",
        "rubber-info",
        "rubber-pipe",
    ),
    cmdclass = {
        "build": build,
        "install": install,
        "clean": clean,
        "tar": tar,
    },
)
