# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# (c) Sebastian Kapfer 2015
# vim: noet:ts=4
"""
LaTeX document building system for Rubber.

This module contains all the code in Rubber that actually does the job of
building a LaTeX document from start to finish.
"""

import importlib
import os, os.path, sys
import re
import logging
msg = logging.getLogger (__name__)
import rubber.util
from rubber.util import _, parse_line
import rubber.depend
import rubber.contents
import rubber.latex_modules

from rubber.tex import EOF, OPEN, SPACE, END_LINE

#----  Module handler  ----{{{1

class Modules:
    """
    This class gathers all operations related to the management of modules.
    The modules are    searched for first in the current directory, then as
    scripts in the 'modules' directory in the program's data directory, then
    as a Python module in the package `rubber.latex'.
    """
    def __init__ (self, latexdep):
        self.latexdep = latexdep
        self.objects = {}
        self.commands = {}

    def __getitem__ (self, name):
        """
        Return the module object of the given name.
        """
        return self.objects[name]

    def __contains__ (self, name):
        """
        Check if a given module is loaded.
        """
        return name in self.objects

    def register (self, name, opt=None, maybe_missing = False):
        """
        Attempt to register a module with the specified name. If the module is
        already loaded, do nothing. If it is found and not yet loaded, then
        load it, initialise it (using the opt passed as optional argument)
        and run any delayed commands for it.
        """
        if name in self:
            msg.debug(_("module %s already registered") % name)
            return

        assert name != ''

        # Warn about obsolete user modules.

        rub_searchpath = [
            "",                                # working dir
            rubber.latex_modules.__path__[0],  # builtin rubber modules
            # these are different from pre-1.4 search paths to avoid pulling
            # in old modules from previous installs.
            "/usr/local/share/rubber/latex_modules",
            "/usr/share/rubber/latex_modules",
        ]
        for path in rub_searchpath:
            file = os.path.join(path, name + ".rub")
            if os.path.exists(file):
                msg.error (rubber.util._format ({'file':file},
                    'Ignoring %s. Please contact the authors for a replacement.' % file))
        for directory in (
            "",                                # working dir
            "/usr/local/share/rubber/latex_modules",
            "/usr/share/rubber/latex_modules",
        ):
            path = os.path.join(path, name + ".py")
            if (os.path.exists (path)):
                msg.error (rubber.util._format ({'file':file},
                    'Ignoring %s. Please contact the authors for a replacement.' % path))

        # Import the built-in python module, if any.

        try:
            source = importlib.import_module ('rubber.latex_modules.' + name)
        except ImportError:
            if maybe_missing:
                msg.debug (_("no support found for %s") % name)
                return
            else:
                raise rubber.GenericError (_("module %s not found") % name)
        mod = source.Module (document=self.latexdep, opt=opt)
        msg.debug (_("built-in module %s registered") % name)

        # Run any delayed commands.

        if name in self.commands:
            for (cmd, args) in self.commands[name]:
                mod.command (cmd, args)
            del self.commands[name]

        self.objects[name] = mod

    def command (self, mod, cmd, args):
        """
        Send a command to a particular module. If this module is not loaded,
        store the command so that it will be sent when the module is registered.
        """
        if mod in self.objects:
            self.objects[mod].command(cmd, args)
        else:
            if mod not in self.commands:
                self.commands[mod] = []
            self.commands[mod].append((cmd, args))


#----  Log parser  ----{{{1

re_loghead = re.compile("This is [0-9a-zA-Z-]*")
re_file = re.compile("(\\((?P<file>[^ \n\t(){}]*)|\\))")
re_badbox = re.compile(r"(Ov|Und)erfull \\[hv]box ")
re_rawbox = re.compile (r'^\\[hv]box\(')
re_line = re.compile(r"(l\.(?P<line>[0-9]+)( (?P<code>.*))?$|<\*>)")
re_cseq = re.compile(r".*(?P<seq>(\\|\.\.\.)[^ ]*) ?$")
re_macro = re.compile(r"^(?P<macro>\\.*) ->")
re_page = re.compile("\[(?P<num>[0-9]+)\]")
re_atline = re.compile(
"( detected| in paragraph)? at lines? (?P<line>[0-9]*)(--(?P<last>[0-9]*))?")
re_reference = re.compile("LaTeX Warning: Reference `(?P<ref>.*)' \
on page (?P<page>[0-9]*) undefined on input line (?P<line>[0-9]*)\\.$")
re_label = re.compile("LaTeX Warning: (?P<text>Label .*)$")
re_warning = re.compile(
"(LaTeX|Package)( (?P<pkg>.*))? Warning: (?P<text>.*)$")
re_online = re.compile("(; reported)? on input line (?P<line>[0-9]*)")
re_ignored = re.compile("; all text was ignored after line (?P<line>[0-9]*).$")

class LogCheck (object):
    """
    This class performs all the extraction of information from the log file.
    For efficiency, the instances contain the whole file as a list of strings
    so that it can be read several times with no disk access.
    """
    #-- Initialization {{{2

    def __init__ (self):
        self.lines = None

    def readlog (self, name, limit):
        """
        Read the specified log file, checking that it was produced by the
        right compiler. Returns False if the log file is invalid or does not
        exist.
        """
        self.lines = None
        try:
            with open (name, encoding='utf_8', errors='replace') as fp:
                line = fp.readline ()
                if not line or not re_loghead.match (line):
                    msg.debug (_('empty log'))
                    return False
                # do not read the whole log unconditionally
                whole_file = fp.read (limit)
                self.lines = whole_file.split ('\n')
                if fp.read (1) != '':
                    # more data to be read
                    msg.warning (_('log file is very long, and will not be read completely.'))
            return True
        except IOError:
            msg.debug (_('IO Error with log'))
            return False

    #-- Process information {{{2

    def errors (self):
        """
        Returns true if there was an error during the compilation.
        """
        skipping = 0
        for line in self.lines:
            if line.strip() == "":
                skipping = 0
                continue
            if skipping:
                continue
            m = re_badbox.match(line)
            if m:
                skipping = 1
                continue
            if line[0] == "!":
                # We check for the substring "pdfTeX warning" because pdfTeX
                # sometimes issues warnings (like undefined references) in the
                # form of errors...

                if line.find("pdfTeX warning") == -1:
                    return 1
        return 0

    #-- Information extraction {{{2

    def continued (self, line):
        """
        Check if a line in the log is continued on the next line. This is
        needed because TeX breaks messages at 79 characters per line. We make
        this into a method because the test is slightly different in Metapost.
        """
        return len(line) == 79

    def parse (self, errors=0, boxes=0, refs=0, warnings=0):
        """
        Parse the log file for relevant information. The named arguments are
        booleans that indicate which information should be extracted:
        - errors: all errors
        - boxes: bad boxes
        - refs: warnings about references
        - warnings: all other warnings
        The function returns a generator. Each generated item is a dictionary
        that contains (some of) the following entries:
        - kind: the kind of information ("error", "box", "ref", "warning")
        - text: the text of the error or warning
        - code: the piece of code that caused an error
        - file, line, last, pkg: as used by Message.format_pos.
        """
        if not self.lines:
            return
        last_file = None
        pos = [last_file]
        page = 1
        parsing = 0    # 1 if we are parsing an error's text
        skipping = 0   # 1 if we are skipping text until an empty line
        something = 0  # 1 if some error was found
        prefix = None  # the prefix for warning messages from packages
        accu = ""      # accumulated text from the previous line
        macro = None   # the macro in which the error occurs
        cseqs = {}     # undefined control sequences so far
        for line in self.lines:
            # TeX breaks messages at 79 characters, just to make parsing
            # trickier...

            if not parsing and self.continued(line):
                accu += line
                continue
            line = accu + line
            accu = ""

            # Text that should be skipped (from bad box messages)

            if prefix is None and line == "":
                skipping = 0
                continue

            if skipping:
                continue

            # Errors (including aborted compilation)

            if parsing:
                if error == "Undefined control sequence.":
                    # This is a special case in order to report which control
                    # sequence is undefined.
                    m = re_cseq.match(line)
                    if m:
                        seq = m.group("seq")
                        if seq in cseqs:
                            error = None
                        else:
                            cseqs[seq] = None
                            error = "Undefined control sequence %s." % m.group("seq")
                m = re_macro.match(line)
                if m:
                    macro = m.group("macro")
                m = re_line.match(line)
                if m:
                    parsing = 0
                    skipping = 1
                    pdfTeX = line.find("pdfTeX warning") != -1
                    if error is not None and ((pdfTeX and warnings) or (errors and not pdfTeX)):
                        if pdfTeX:
                            d = {
                                "kind": "warning",
                                "pkg": "pdfTeX",
                                "text": error[error.find(":")+2:]
                            }
                        else:
                            d =    {
                                "kind": "error",
                                "text": error
                            }
                        d.update( m.groupdict() )
                        m = re_ignored.search(error)
                        if m:
                            d["file"] = last_file
                            if "code" in d:
                                del d["code"]
                            d.update( m.groupdict() )
                        elif pos[-1] is None:
                            d["file"] = last_file
                        else:
                            d["file"] = pos[-1]
                        if macro is not None:
                            d["macro"] = macro
                            macro = None
                        yield d
                elif line[0] == "!":
                    error = line[2:]
                elif line[0:3] == "***":
                    parsing = 0
                    skipping = 1
                    if errors:
                        yield    {
                            "kind": "abort",
                            "text": error,
                            "why" : line[4:],
                            "file": last_file
                            }
                elif line[0:15] == "Type X to quit ":
                    parsing = 0
                    skipping = 0
                    if errors:
                        yield    {
                            "kind": "error",
                            "text": error,
                            "file": pos[-1]
                            }
                continue

            if line.startswith ('!'):
                error = line[2:]
                parsing = 1
                continue

            if line == "Runaway argument?":
                error = line
                parsing = 1
                continue

            if line[:17] == "Output written on":
                continue

            if line.startswith ('Missing character: '):
                error = line
                parsing = 0
                continue

            # Long warnings

            if prefix is not None:
                if line[:len(prefix)] == prefix:
                    text.append(line[len(prefix):].strip())
                else:
                    text = " ".join(text)
                    m = re_online.search(text)
                    if m:
                        info["line"] = m.group("line")
                        text = text[:m.start()] + text[m.end():]
                    if warnings:
                        info["text"] = text
                        d = { "kind": "warning" }
                        d.update( info )
                        yield d
                    prefix = None
                continue

            # Undefined references

            m = re_reference.match(line)
            if m:
                if refs:
                    d =    {
                        "kind": "warning",
                        "text": _("Reference `%s' undefined.") % m.group("ref"),
                        "file": pos[-1]
                        }
                    d.update( m.groupdict() )
                    yield d
                continue

            m = re_label.match(line)
            if m:
                if refs:
                    d =    {
                        "kind": "warning",
                        "file": pos[-1]
                        }
                    d.update( m.groupdict() )
                    yield d
                continue

            # Other warnings

            if line.find("Warning") != -1:
                m = re_warning.match(line)
                if m:
                    info = m.groupdict()
                    info["file"] = pos[-1]
                    info["page"] = page
                    if info["pkg"] is None:
                        del info["pkg"]
                        prefix = ""
                    else:
                        prefix = ("(%s)" % info["pkg"])
                    prefix = prefix.ljust(m.start("text"))
                    text = [info["text"]]
                continue

            # Bad box messages

            m = re_badbox.match(line)
            if m:
                if boxes:
                    mpos = { "file": pos[-1], "page": page }
                    m = re_atline.search(line)
                    if m:
                        md = m.groupdict()
                        for key in "line", "last":
                            if md[key]: mpos[key] = md[key]
                        line = line[:m.start()]
                    d =    {
                        "kind": "warning",
                        "text": line
                        }
                    d.update( mpos )
                    yield d
                skipping = 1
                continue

            # If the user asks to see the full bad box in the log,
            # each line represents a character and may contain a
            # closing parenthesis. This would confuse update_file().
            # The human-readable part has already been reported.
            if re_rawbox.match (line):
                skipping = 1
                continue

            # If there is no message, track source names and page numbers.

            last_file = self.update_file(line, pos, last_file)
            page = self.update_page(line, page)

    def get_errors (self):
        return self.parse(errors=1)
    def get_boxes (self):
        return self.parse(boxes=1)
    def get_references (self):
        return self.parse(refs=1)
    def get_warnings (self):
        return self.parse(warnings=1)

    def update_file (self, line, stack, last):
        """
        Parse the given line of log file for file openings and closings and
        update the list `stack'. Newly opened files are at the end, therefore
        stack[1] is the main source while stack[-1] is the current one. The
        first element, stack[0], contains the value None for errors that may
        happen outside the source. Return the last file from which text was
        read (the new stack top, or the one before the last closing
        parenthesis).
        """
        while True:
            m = re_file.search (line)
            if not m:
                return last
            if line[m.start()] == '(':
                last = m.group("file")
                stack.append(last)
            else:
                last = stack.pop ()
            line = line[m.end():]

    def update_page (self, line, before):
        """
        Parse the given line and return the number of the page that is being
        built after that line, assuming the current page before the line was
        `before'.
        """
        ms = re_page.findall(line)
        if ms == []:
            return before
        return int(ms[-1]) + 1

#----  Parsing and compiling  ----{{{1

re_command = re.compile("%[% ]*rubber: *(?P<cmd>[^ ]*) *(?P<arg>.*).*")

class SourceParser (rubber.tex.Parser):
    """
    Extends the general-purpose TeX parser to handle Rubber directives in the
    comment lines.
    """
    def __init__ (self, file, dep):
        super (SourceParser, self).__init__(file)
        self.latex_dep = dep

    def read_line (self):
        while rubber.tex.Parser.read_line(self):
            match = re_command.match(self.line.strip())
            if match is None:
                return True

            vars = self.latex_dep.vars.copy ()
            vars ['line'] = self.pos_line
            args = parse_line(match.group("arg"), vars)

            self.latex_dep.command(match.group("cmd"), args, vars)
        return False

    def skip_until (self, expr):
        regexp = re.compile(expr)
        while rubber.tex.Parser.read_line(self):
            match = regexp.match(self.line)
            if match is None:
                continue
            self.line = self.line[match.end():]
            self.pos_char += match.end()
            return

class EndDocument (Exception):
    """ This is the exception raised when \\end{document} is found. """
    pass

class EndInput (Exception):
    """ This is the exception raised when \\endinput is found. """
    pass

class LaTeXDep (rubber.depend.Node):
    """
    This class represents dependency nodes for LaTeX compilation. It handles
    the cyclic LaTeX compilation until a stable output, including actual
    compilation (with a parametrable executable) and possible processing of
    compilation results (e.g. running BibTeX).

    Before building (or cleaning) the document, the method `parse' must be
    called to load and configure all required modules. Text lines are read
    from the files and parsed to extract LaTeX macro calls. When such a macro
    is found, a handler is searched for in the `hooks' dictionary. Handlers
    are called with one argument: the dictionary for the regular expression
    that matches the macro call.
    """

    #--  Initialization  {{{2

    def __init__ (self, env, path, jobname):
        """
        Initialize the environment. This prepares the processing steps for the
        given file (all steps are initialized empty) and sets the regular
        expressions and the hook dictionary.

        path specifies the main source for the document. The exact path and file name
        are determined, and the source building process is updated if needed,
        according the the source file's extension. The argument
        'jobname' specifies the job name to something else that
        the base of the file name.
        """
        super ().__init__ ()
        self.env = env

        self.log = LogCheck()
        self.modules = Modules(self)

        self.vars = {
            "source": None,
            "target": None,
            "job": None,
        }
        self.arguments = []
        self.src_specials = ""
        self.logfile_limit = 1000000
        self.program = 'latex'
        self.engine = 'TeX'
        self.cmdline = ["\\nonstopmode", "\\input{%s}"]

        # the initial hooks:

        self.hooks_version = 0
        self.hooks = {
            "begin": ("a", self.h_begin),
            "end": ("a", self.h_end),
            "pdfoutput": ("", self.h_pdfoutput),
            "input" : ("", self.h_input),
            "include" : ("a", self.h_include),
            "includeonly": ("a", self.h_includeonly),
            "usepackage" : ("oa", self.h_usepackage),
            "RequirePackage" : ("oa", self.h_usepackage),
            "documentclass" : ("oa", self.h_documentclass),
            "LoadClass" : ("oa", self.h_documentclass),
            # LoadClassWithOptions doesn't take optional arguments, but
            # we recycle the same handler
            "LoadClassWithOptions" : ("oa", self.h_documentclass),
            "tableofcontents" : ("", self.h_tableofcontents),
            "listoffigures" : ("", self.h_listoffigures),
            "listoftables" : ("", self.h_listoftables),
            "bibliography" : ("a", self.h_bibliography),
            "bibliographystyle" : ("a", self.h_bibliographystyle),
            "endinput" : ("", self.h_endinput)
        }
        self.begin_hooks = {
            "verbatim": self.h_begin_verbatim,
            "verbatim*": lambda loc: self.h_begin_verbatim(loc, env="verbatim\\*")
        }
        self.end_hooks = {
            "document": self.h_end_document
        }

        self.include_only = {}

        # FIXME interim solution for BibTeX module -- rewrite it.
        self.aux_files = []

        # description of the building process:

        self.onchange = []

        # state of the builder:

        self.processed_sources = {}

        self.failed_module = None

        assert os.path.exists(path)
        assert len (self.sources) == 0
        self.vars['source'] = path
        (src_path, name) = os.path.split(path)
        # derive jobname, which latex uses as the basename for all output
        (job, _) = os.path.splitext(name)
        if jobname is None:
            self.set_job = 0
        else:
            self.set_job = 1
            job = jobname
        self.vars['job'] = job
        if src_path == "":
            src_path = "."
        else:
            self.env.path.append(src_path)

        if '"' in path:
            msg.error(_("The filename contains \", latex cannot handle this."))
            return 1
        if any (c in path for c in " \n\t()"):
            msg.warning (_("Source path uses special characters, error tracking might get confused."))

        self.add_product (self.basename (with_suffix=".dvi"))
        self.add_product (self.basename (with_suffix=".log"))

        # always expect a primary aux file
        self.new_aux_file (self.basename (with_suffix=".aux"))
        self.add_product (self.basename (with_suffix=".synctex.gz"))

    def basename (self, with_suffix=""):
        return self.vars["job"] + with_suffix

    def register_post_processor (self, old_suffix, new_suffix):
        if self.env.final != self \
           and not self.primary_product ().endswith (old_suffix):
            raise GenericError (_("there is already a post-processor registered"))
        self.replace_product (self.basename (with_suffix=new_suffix))

    def new_aux_file (self, aux_file):
        """Register a new latex .aux file"""
        self.add_source (aux_file)
        self.add_product (aux_file)
        self.aux_files.append (aux_file)

    def includeonly (self, files):
        """
        Use partial compilation, by appending a call to \\includeonly on the
        command line on compilation.
        The 'files' string is copied verbatim.
        It should be a comma-separated list of file names.
        """
        if self.engine == "VTeX":
            msg.error(_("I don't know how to do partial compilation on VTeX."))
            return
        if self.cmdline[-2][:13] == "\\includeonly{":
            self.cmdline[-2] = "\\includeonly{" + files + "}"
        else:
            self.cmdline.insert(-1, "\\includeonly{" + files + "}")
        for f in files.split (','):
            self.include_only[f] = None

    def source (self):
        """
        Return the main source's complete filename.
        """
        return self.vars['source']

    #--  LaTeX source parsing  {{{2

    def parse (self):
        """
        Parse the source for packages and supported macros.
        """
        try:
            self.process(self.source())
        except EndDocument:
            pass
        msg.debug (_("dependencies: %s"), " ".join (self.sources))

    def parse_file (self, file):
        """
        Process a LaTeX source. The file must be open, it is read to the end
        calling the handlers for the macro calls. This recursively processes
        the included sources.
        """
        parser = SourceParser(file, self)
        hooks_version = -1
        while True:
            if hooks_version != self.hooks_version:
                parser.set_hooks(self.hooks.keys())
                hooks_version = self.hooks_version
            token = parser.next_hook()
            if token.cat == EOF:
                break
            format, function = self.hooks[token.val]
            args = []
            for arg in format:
                if arg == '*':
                    args.append(parser.get_latex_star())
                elif arg == 'a':
                    args.append(parser.get_argument_text())
                elif arg == 'o':
                    args.append(parser.get_latex_optional_text())
            self.parser = parser
            self.vars['line'] = parser.pos_line
            function(self.vars, *args)

    def process (self, path):
        """
        This method is called when an included file is processed. The argument
        must be a valid file name.
        """
        if path in self.processed_sources:
            msg.debug(_("%s already parsed") % path)
            return
        self.processed_sources[path] = None
        self.add_source (path)

        try:
            saved_vars = self.vars.copy ()
            try:
                msg.debug(_("parsing %s") % path)
                self.vars ["file"] = path
                self.vars ["line"] = None
                with open (path, encoding='utf_8', errors='replace') as file:
                    self.parse_file(file)

            finally:
                self.vars = saved_vars
                msg.debug(_("end of %s") % path)

        except EndInput:
            pass

    def input_file (self, name, loc={}):
        """
        Treat the given name as a source file to be read. If this source can
        be the result of some conversion, then the conversion is performed,
        otherwise the source is parsed. The returned value is a couple
        (name,dep) where `name' is the actual LaTeX source and `dep' is
        its dependency node. The return value is (None,None) if the source
        could neither be read nor built.
        """
        if name.find("\\") >= 0 or name.find("#") >= 0:
            return None

        for path in self.env.path:

            pname = os.path.join(path, name)
            dep = self.env.convert(pname, suffixes=[".tex",""], context=self.vars)
            if isinstance (dep, str):
                self.process (dep)
                return dep
            if isinstance (dep, rubber.depend.Node):
                file = dep.primary_product ()
                # Do not process this source.
                self.add_source (file)
                return file
            assert dep is None

            file = self.env.find_file (name, ".tex")
            if file is not None:
                self.process(file)
                return file

        return None

    #--  Directives  {{{2

    def command (self, cmd, args, pos=None):
        """
        Execute the rubber command 'cmd' with arguments 'args'. This is called
        when a command is found in the source file or in a configuration file.
        A command name of the form 'foo.bar' is considered to be a command
        'bar' for module 'foo'. The argument 'pos' describes the position
        (file and line) where the command occurs.
        """
        if pos is None:
            pos = self.vars
        # Calls to this method are actually translated into calls to "do_*"
        # methods, except for calls to module directives.
        lst = cmd.split(".", 1)
        if len(lst) > 1:
            self.modules.command(lst[0], lst[1], args)
        else:
            try:
                handler = getattr (self, "do_" + cmd)
            except AttributeError:
                raise rubber.GenericError (rubber.util._format (pos, _("unknown directive '%s'") % cmd))
            msg.debug (_("directive: %s %s") % (cmd, ' '.join (args)))
            handler (args)

    def do_alias (self, args):
        if len (args) != 2:
            raise rubber.SyntaxError (_("invalid syntax for directive '%s'") % "alias")
        name, val = args
        try:
            h = self.hooks [val]
        except KeyError:
            raise rubber.SyntaxError (_("cannot alias unknown name %s") % val)
        self.hooks [name] = h
        self.hooks_version += 1

    def do_clean (self, args):
        for arg in args:
            self.add_product (arg)

    def do_depend (self, args):
        for arg in args:
            file = self.env.find_file(arg)
            if file:
                self.add_source(file)
            else:
                msg.warning (rubber.util._format (self.vars, _("dependency '%s' not found") % arg))

    def do_make (self, args):
        if len (args) % 2 != 1:
            raise rubber.SyntaxError (_("invalid syntax for directive '%s'") % "make")
        file = args [0]
        vars = { "target": file }
        for i in range (1, len (args), 2):
            if args [i] == "from":
                vars ["source"] = args [i + 1]
            elif args [i] == "with":
                vars ["name"] = args[1 + 1]
            else:
                raise rubber.SyntaxError (_("invalid syntax for directive '%s'") % "make")
        self.env.conv_set(file, vars)

    def do_module (self, args):
        if 0 == len (args) or 2 < len (args):
            raise rubber.SyntaxError (_("invalid syntax for directive '%s'") % "module")
        self.modules.register (*args)

    def do_onchange (self, args):
        if len (args) != 2:
            raise rubber.SyntaxError (_("invalid syntax for directive '%s'") % "onchange")
        file, cmd = args
        if self.env.is_in_unsafe_mode_:
            # A list, because we will update the snapshot later.
            self.onchange.append ([file, rubber.contents.snapshot (file), cmd])
        else:
            msg.warning (_("Rubber directive 'onchange' is valid only in unsafe mode"))

    def do_paper (self, args):
        msg.warning (_("Rubber directive 'paper' is no longer supported"))

    def do_path (self, args):
        if len (args) != 1:
            raise rubber.SyntaxError (_("invalid syntax for directive '%s'") % "path")
        name = args [0]
        self.env.path.append(name)

    def do_read (self, args):
        if len (args) != 1:
            raise rubber.SyntaxError (_("invalid syntax for directive '%s'") %  "read")
        name = args [0]
        saved_vars = self.vars
        try:
            self.vars = self.vars.copy ()
            self.vars ["file"] = name
            self.vars ["line"] = None
            with open (name, encoding='utf_8', errors='replace') as file:
                lineno = 0
                for line in file:
                    lineno += 1
                    line = line.strip()
                    if line == "" or line[0] == "%":
                        continue
                    self.vars["line"] = lineno
                    lst = parse_line(line, self.vars)
                    self.command(lst[0], lst[1:])
        except IOError:
            msg.warning (rubber.util._format (self.vars, _("cannot read option file %s") % name))
        finally:
            self.vars = saved_vars

    def do_rules (self, args):
        if len (args) != 1:
            raise rubber.SyntaxError (rubber.util._format (self.vars, _("invalid syntax for directive '%s'") % cmd))
        file = args [0]
        name = self.env.find_file(file)
        if name is None:
            msg.warning (rubber.util._format (self.vars, _("cannot read rule file %s") % file))
        else:
            self.env.converter.read_ini(name)

    def do_set (self, args):
        if len (args) != 2:
            raise rubber.SyntaxError (rubber.util._format (self.vars, _("invalid syntax for directive '%s'") % cmd))
        name, val = args
        if name in ('arguments',):
            msg.warning (_("cannot set list-type variable to scalar: set %s %s (ignored; use setlist, not set)") % (name, val))
        elif name in ('job',):
            msg.warning (_("variable %s is read-only, please see the manual") % name)
        elif name in ('logfile_limit',):
                try:
                    val = int (val)
                except:
                    msg.warning (_("cannot set int variable %s to value %s (ignored)") % (name, val))
                else:
                    setattr (self, name, val)
        elif name in ('src-specials',):
            setattr (self, name, val)
        elif name in ('engine', 'file', 'line',):
            msg.warning (_("variable %s is deprecated, please see the manual") % name)
        else:
            msg.warning (rubber.util._format (self.vars, _("unknown variable: %s") % name))

    def do_shell_escape (self, args):
        if len (args) != 0:
            raise rubber.SyntaxError (rubber.util._format (self.vars, _("invalid syntax for directive '%s'") % cmd))
        self.env.doc_requires_shell_ = True

    def do_synctex (self, args):
        if len (args) != 0:
            raise rubber.SyntaxError (_("invalid syntax for directive '%s'") % cmd)
        self.env.synctex = True

    def do_setlist (self, args):
        if len (args) == 0:
            raise rubber.SyntaxError (_("invalid syntax for directive '%s'") % cmd)
        name, val = args [0], args [1:]
        if name in ('arguments',):
            self.arguments.extend (val)
        else:
            msg.warning (rubber.util._format (self.vars, _("unknown list variable: %s") % name))

    def do_produce (self, args):
        for arg in args:
            self.add_product(arg)

    def do_watch (self, args):
        for arg in args:
            self.watch_file(arg)

    #--  Macro handling  {{{2

    def hook_macro (self, name, format, fun):
        self.hooks[name] = (format, fun)
        self.hooks_version += 1

    def hook_begin (self, name, fun):
        self.begin_hooks[name] = fun

    def hook_end (self, name, fun):
        self.end_hooks[name] = fun

    # Now the macro handlers:

    def h_begin (self, loc, env):
        if env in self.begin_hooks:
            self.begin_hooks[env](loc)

    def h_end (self, loc, env):
        if env in self.end_hooks:
            self.end_hooks[env](loc)

    def h_pdfoutput (self, loc):
        """
        Called when \\pdfoutput is found. Tries to guess if it is a definition
        that asks for the output to be in PDF or DVI.
        """
        parser = self.parser
        token = parser.get_token()
        if token.raw == '=':
            token2 = parser.get_token()
            if token2.raw == '0':
                mode = 0
            elif token2.raw == '1':
                mode = 1
            else:
                parser.put_token(token2)
                return
        elif token.raw == '0':
            mode = 0
        elif token.raw == '1':
            mode = 1
        else:
            parser.put_token(token)
            return

        if mode == 0:
            if 'pdftex' in self.modules:
                self.modules['pdftex'].mode_dvi()
            else:
                self.modules.register ('pdftex', opt='dvi')
        else:
            if 'pdftex' in self.modules:
                self.modules['pdftex'].mode_pdf()
            else:
                self.modules.register('pdftex')

    def h_input (self, loc):
        """
        Called when an \\input macro is found. This calls the `process' method
        if the included file is found.
        """
        token = self.parser.get_token()
        if token.cat == OPEN:
            file = self.parser.get_group_text()
        else:
            file = ""
            while token.cat not in (EOF, SPACE, END_LINE):
                file += token.raw
                token = self.parser.get_token()
        _ = self.input_file(file, loc)

    def h_include (self, loc, filename):
        """
        Called when an \\include macro is found. This includes files into the
        source in a way very similar to \\input, except that LaTeX also
        creates .aux files for them, so we have to notice this.
        """
        if self.include_only and filename not in self.include_only:
            return
        file = self.input_file(filename, loc)
        if file:
            self.new_aux_file (filename + ".aux")

    def h_includeonly (self, loc, files):
        """
        Called when the macro \\includeonly is found, indicates the
        comma-separated list of files that should be included, so that the
        othe \\include are ignored.
        """
        self.include_only = {}
        for name in files.split(","):
            name = name.strip()
            if name != "":
                self.include_only[name] = None

    def h_documentclass (self, loc, opt, name):
        """
        Called when the macro \\documentclass is found. It almost has the same
        effect as `usepackage': if the source's directory contains the class
        file, in which case this file is treated as an input, otherwise a
        module is searched for to support the class.
        """
        file = self.env.find_file(name + ".cls")
        if file:
            self.process(file)
        else:
            self.modules.register (name, opt=opt, maybe_missing=True)

    def h_usepackage (self, loc, opt, names):
        """
        Called when a \\usepackage macro is found. If there is a package in the
        directory of the source file, then it is treated as an include file
        otherwise it is treated as a package.
        """
        for name in names.split(","):
            name = name.strip()
            if name == '': continue  # \usepackage{a,}
            file = self.env.find_file(name + ".sty")
            if file:
                self.process(file)
            else:
                self.modules.register (name, opt=opt, maybe_missing=True)

    def h_tableofcontents (self, loc):
        self.add_product(self.basename (with_suffix=".toc"))
        self.add_source (self.basename (with_suffix=".toc"))
    def h_listoffigures (self, loc):
        self.add_product(self.basename (with_suffix=".lof"))
        self.add_source (self.basename (with_suffix=".lof"))
    def h_listoftables (self, loc):
        self.add_product(self.basename (with_suffix=".lot"))
        self.add_source (self.basename (with_suffix=".lot"))

    def h_bibliography (self, loc, names):
        """
        Called when the macro \\bibliography is found. This method actually
        registers the module bibtex (if not already done) and registers the
        databases.
        """
        self.modules.register ("bibtex")
        # This registers the actual hooks, so that subsequent occurrences of
        # \bibliography and \bibliographystyle will be caught by the module.
        # However, the first time, we have to call the hooks from here. The
        # line below assumes that the new hook has the same syntax.
        self.hooks['bibliography'][1](loc, names)

    def h_bibliographystyle (self, loc, name):
        """
        Called when \\bibliographystyle is found. This registers the module
        bibtex (if not already done) and calls the method set_style() of the
        module.
        """
        self.modules.register ("bibtex")
        # The same remark as in 'h_bibliography' applies here.
        self.hooks['bibliographystyle'][1](loc, name)

    def h_begin_verbatim (self, loc, env="verbatim"):
        """
        Called when \\begin{verbatim} is found. This disables all macro
        handling and comment parsing until the end of the environment. The
        optional argument 'end' specifies the end marker, by default it is
        "\\end{verbatim}".
        """
        self.parser.skip_until(r"[ \t]*\\end\{%s\}.*" % env)

    def h_endinput (self, loc):
        """
        Called when \\endinput is found. This stops the processing of the
        current input file, thus ignoring any code that appears afterwards.
        """
        raise EndInput

    def h_end_document (self, loc):
        """
        Called when \\end{document} is found. This stops the processing of any
        input file, thus ignoring any code that appears afterwards.
        """
        raise EndDocument

    #--  Compilation steps  {{{2

    def compile (self):
        """
        Run one LaTeX compilation on the source. Return true on success or
        false if errors occured.
        """
        msg.info (_("compiling %s"), self.source)

        file = self.source()

        if file.find(" ") >= 0:
            file = '"%s"' % file

        cmd = [self.program]

        if self.set_job:
            if self.engine == "VTeX":
                msg.error(_("I don't know how set the job name with VTeX."))
            else:
                cmd.append("-jobname=" + self.basename ())

        specials = self.src_specials
        if specials != "":
            if self.engine == "VTeX":
                msg.warning(_("I don't know how to make source specials with VTeX."))
                self.src_specials = ""
            elif specials == "yes":
                cmd.append("-src-specials")
            else:
                cmd.append("-src-specials=" + specials)

        if self.env.is_in_unsafe_mode_:
            cmd.append ('--shell-escape')
        elif self.env.doc_requires_shell_:
            msg.error (_("the document tries to run external programs which could be dangerous.  use rubber --unsafe if the document is trusted."))

        if self.env.synctex:
            cmd.append ("-synctex=1")

        # arguments inserted by the document allowed only in unsafe mode, since
        # this could do arbitrary things such as enable shell escape (write18)
        if self.env.is_in_unsafe_mode_:
            cmd.extend (self.arguments)
        elif len (self.arguments) > 0:
            msg.error (_("the document tries to modify the LaTeX command line which could be dangerous.  use rubber --unsafe if the document is trusted."))

        cmd.extend (x.replace ("%s", file) for x in self.cmdline)

        # Remove the CWD from elements in the path, to avoid potential problems
        # with special characters if there are any (except that ':' in paths
        # is not handled).

        inputs = ":".join (self.env.path)

        if inputs == "":
            env = {}
        else:
            inputs = inputs + ":" + os.getenv("TEXINPUTS", "")
            env = {"TEXINPUTS": inputs}
        if rubber.util.execute (cmd, env=env) != 0:
            msg.error(_("Running %s resulted in a non-zero exit status."), cmd [0])
            return False

        if not self.parse_log ():
            msg.error(_("Running %s failed.") % cmd[0])
            return False
        if self.log.errors():
            return False
        if not os.access (self.primary_product (), os.F_OK):
            msg.error (_("Output file `%s' was not produced."),
                       self.primary_product ())
            return False
        return True

    def parse_log (self):
        logfile_name = self.basename (with_suffix=".log")
        logfile_limit = self.logfile_limit
        return self.log.readlog (logfile_name, logfile_limit)

    def pre_compile (self):
        """
        Prepare the source for compilation using package-specific functions.
        This function must return False on failure.
        """
        msg.debug(_("building additional files..."))

        for mod in self.modules.objects.values():
            if not mod.pre_compile():
                self.failed_module = mod
                return False
        return True

    def post_compile (self):
        """
        Run the package-specific operations that are to be performed after
        each compilation of the main source. Returns true on success or false
        on failure.
        """
        msg.debug(_("running post-compilation scripts..."))

        for l in self.onchange:
            (file, old_contents, cmd) = l
            new = rubber.contents.snapshot (file)
            if old_contents != new:
                # An exception should already have been raised if the
                # file has disappeared.
                assert new != rubber.contents.NO_SUCH_FILE
                l [1] = new
                msg.info (_("running %s") % cmd)
                # FIXME portability issue: explicit reference to shell
                if rubber.util.execute (("sh", "-c", cmd)) != 0:
                    msg.error (_("command '%s' returned a non-zero status"), cmd)
                    return False

        for mod in self.modules.objects.values():
            if not mod.post_compile():
                self.failed_module = mod
                return False
        return True

    def clean (self):
        """
        Run clean method of LaTeX modules.
        """
        msg.debug (_("cleaning LaTeX modules..."))
        for mod in self.modules.objects.values():
            mod.clean()

    #--  Building routine  {{{2

    def run (self):
        """
        Run the building process until the last compilation, or stop on error.
        This method supposes that the inputs were parsed to register packages
        and that the LaTeX source is ready. If the second (optional) argument
        is true, then at least one compilation is done. As specified by the
        parent class, the method returns True on success and False on
        failure.
        """
        if not self.pre_compile():
            return False

        # If an error occurs after this point, it will be while LaTeXing.
        self.failed_module = None

        if not self.compile():
            return False
        if not self.post_compile():
            return False

        return True

    #--  Utility methods  {{{2

    def get_errors (self):
        if self.failed_module is None:
            return self.log.get_errors()
        else:
            return self.failed_module.get_errors()

    def watch_file (self, filename):
        """
        Register the given file (typically "jobname.toc" or such) to be
        watched. When the file changes during a compilation, it means that
        another compilation has to be done.
        """
        self.add_source (filename)

    def remove_suffixes (self, list):
        """
        Remove all files derived from the main source with one of the
        specified suffixes.
        """
        for suffix in list:
            file = self.basename (with_suffix=suffix)
            if os.path.exists (file):
                msg.info (_("removing %s"), file)
                os.remove (file)
