# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# (c) Sebastian Kapfer, 2015
# vim: noet:ts=4
"""
This is the command line interface for Rubber.
"""

import os.path
import sys
import getopt
import shutil
import tempfile
# bzip2 and/or gzip may be imported depending on command line options.
import rubber.converters.compressor
import rubber.converters.latex
import rubber.converters.literate
import rubber.depend
import rubber.environment
from rubber.util import _
import logging
msg = logging.getLogger (__name__)
import rubber.util
import rubber.version

# The expected entry point is the main procedure, with one of these
# three values to track the command name (which may differ from
# sys.argv [0] for symbolic links).
RUBBER_PLAIN = 0
RUBBER_PIPE  = 1
RUBBER_INFO  = 2

class CommandLineOptions:
    """
    An instance is built by parse_opts from the command line options, then
    read-only afterwards.

    """
    def __init__ (self, command_name):
        self.max_errors = 10
        self.place = "."
        self.texpath = []
        self.prologue = []
        self.epilogue = []
        self.include_only = None
        self.compress = None
        self.jobname = None
        self.unsafe = False
        self.short = False
        if command_name == RUBBER_PLAIN:
            self.force = False
            self.clean = False
            self.warn_boxes = False
            self.warn_misc = False
            self.warn_refs = False
        elif command_name == RUBBER_PIPE:
            self.keep_temp = False
            self.warn_boxes = False
            self.warn_misc = False
            self.warn_refs = False
        else:
            self.info_action = None

full_help_plain = _("""\
usage: rubber [options] sources...
available options:
  -b, --bzip2              compress the final document with bzip2
      --clean              remove produced files instead of compiling
  -c, --command=CMD        run the directive CMD before parsing (see man page)
  -e, --epilogue=CMD       run the directive CMD after parsing
  -f, --force              force at least one compilation
  -z, --gzip               compress the final document
  -h, --help               display this help
      --inplace            compile the documents from their source directory
      --into=DIR           go to directory DIR before compiling
      --jobname=NAME       set the job name for the first target
  -n, --maxerr=NUM         display at most NUM errors (default: 10)
  -m, --module=MOD[:OPTS]  use module MOD (with options OPTS)
      --only=SOURCES       only include the specified SOURCES
  -o, --post=MOD[:OPTS]    postprocess with module MOD (with options OPTS)
  -d, --pdf                produce a pdf (synonym for -m pdftex or -o ps2pdf)
  -p, --ps                 process through dvips (synonym for -o dvips)
  -q, --quiet              suppress messages
  -r, --read=FILE          read additional directives from FILE
  -S, --src-specials       enable insertion of source specials
      --synctex            enable SyncTeX support
      --unsafe             permits the document to run external commands
  -s, --short              display errors in a compact form
  -I, --texpath=DIR        add DIR to the search path for LaTeX
  -v, --verbose            increase verbosity
      --version            print version information and exit
  -W, --warn=TYPE          report warnings of the given TYPE (see man page)
""")

def parse_opts (command_name):
    """
    Parse the command-line arguments.
    Returns the extra arguments (i.e. the files to operate on), or an
    empty list, if no extra arguments are present.
    Also set the log level according to -q/-v options.
    """
    # This implies that we cannot log from here.
    logLevel = logging.WARNING

    # Set the initial values for options.
    options = CommandLineOptions (command_name)

    try:
        opts, args = getopt.gnu_getopt (
            sys.argv [1:], "I:bc:de:fhklm:n:o:pqr:SsvW:z",
            ["bzip2", "cache", "clean", "command=", "epilogue=", "force", "gzip",
             "help", "inplace", "into=", "jobname=", "keep", "maxerr=",
             "module=", "only=", "post=", "pdf", "ps", "quiet", "read=",
             "readopts=",
             "src-specials", "shell-escape", "synctex", "unsafe", "short", "texpath=", "verbose", "version",
             "boxes", "check", "deps", "errors", "refs", "rules", "warnings",
             "warn="])
    except getopt.GetoptError as e:
        raise rubber.SyntaxError (_("getopt error: %s") % str (e))

    extra = []
    using_dvips = False

    for (opt,arg) in opts:
        # obsolete options
        if opt == "--cache":
            print (_("ignoring unimplemented option %s") % opt)
        elif opt in ("--readopts", "-l", "--landscape" ):
            raise rubber.SyntaxError (_("option %s is no longer supported") % opt)

        # info
        elif opt in ("-h", "--help"):
            if command_name == RUBBER_PLAIN:
                print (full_help_plain)
            elif command_name == RUBBER_PIPE:
                print (full_help_pipe)
            else:
                print (full_help_info)
            sys.exit (0)
        elif opt == "--version":
            print ("Rubber version: %s" % rubber.version.version)
            sys.exit (0)

        # mode of operation
        elif opt == "--clean":
            if command_name != RUBBER_PLAIN:
                raise rubber.SyntaxError (_("--clean only allowed with rubber") )
            options.clean = True

        elif opt in ("-k", "--keep"):
            if command_name == RUBBER_PIPE:
                options.keep_temp = True
            else:
                raise rubber.SyntaxError (_("option %s only makes sense in pipe mode") % opt)

        # compression etc. which affects which products exist
        elif opt in ("-b", "--bzip2", "-z", "--gzip"):
            algo = "bzip2" if opt in ("-b", "--bzip2") else "gzip"
            if options.compress is None:
                options.compress = algo
            elif options.compress != algo:
                raise SyntaxError (_("incompatible options: %s and %s") % (opt, "--" + options.compress))
        elif opt in ("-c", "--command"):
            options.prologue.append(arg)
        elif opt in ("-e", "--epilogue"):
            options.epilogue.append(arg)
        elif opt in ("-f", "--force"):
            if command_name != RUBBER_PLAIN:
                raise rubber.SyntaxError (_("option %s only allowed for rubber") % opt)
            options.force = True
        elif opt == "--inplace":
            if command_name == RUBBER_PIPE:
                raise rubber.SyntaxError (_("option %s does not make sense for rubber-pipe") % opt)
            if options.place != '.':
                raise rubber.SyntaxError (_("only one --inplace/into option allowed"))
            options.place = None
        elif opt == "--into":
            if options.place != '.':
                raise rubber.SyntaxError (_("only one --inplace/into option allowed"))
            options.place = arg
        elif opt == "--jobname":
            options.jobname = arg
        elif opt in ("-n", "--maxerr"):
            try:
                options.max_errors = int(arg)
            except ValueError:
                raise SyntaxError (_('argument for %s must be an integer' % opt))
        elif opt in ("-m", "--module"):
            options.prologue.append("module " +
                arg.replace(":", " ", 1))
        elif opt == "--only":
            if options.include_only is not None:
                raise rubber.SyntaxError (_("only one --only allowed"))
            options.include_only = arg.split(",")
        elif opt in ("-o", "--post"):
            if command_name == RUBBER_INFO:
                raise rubber.SyntaxError (_("%s not allowed for rubber-info") % opt)
            options.epilogue.append("module " +
                arg.replace(":", " ", 1))
        elif opt in ("-d", "--pdf"):
            if using_dvips:
                options.epilogue.append("module ps2pdf")
            else:
                options.prologue.append("module pdftex")
        elif opt in ("-p", "--ps"):
            options.epilogue.append("module dvips")
            using_dvips = True
        elif opt in ("-q", "--quiet"):
            if logLevel < logging.ERROR:
                logLevel += 10
        # we continue to accept --shell-escape for now
        elif opt in ("--unsafe", "--shell-escape"):
            options.unsafe = True
        elif opt in ("-r" ,"--read"):
            options.prologue.append("read " + arg)
        elif opt in ("-S", "--src-specials"):
            options.prologue.append("set src-specials yes")
        elif opt in ("-s", "--short"):
            options.short = True
        elif opt in ("--synctex"):
            options.prologue.append("synctex")
        elif opt in ("-I", "--texpath"):
            options.texpath.append(arg)
        elif opt in ("-v", "--verbose"):
            if logging.DEBUG < logLevel:
                logLevel -= 10
        elif opt in ("-W", "--warn"):
            if command_name == RUBBER_INFO:
                raise rubber.Syntaxerror (_("%s does not make sense with rubber-info") % opt)
            if arg == "all":
                options.warn_boxes = True
                options.warn_misc = True
                options.warn_refs = True
            elif arg == "boxes":
                options.warn_boxes = True
            elif arg == "misc":
                options.warn_misc = True
            elif arg == "refs":
                options.warn_refs = True
            else:
                raise rubber.SyntaxError (_("unexpected value for option %s") % opt)
        elif opt in ("--boxes", "--check", "--deps", "--errors", "--refs", "--rules", "--warnings"):
            if command_name != RUBBER_INFO:
                raise rubber.SyntaxError (_("%s only allowed for rubber-info") % opt)
            new_info_action = opt [2:]
            if options.info_action not in (None, new_info_action):
                raise rubber.SyntaxError (_("error: cannot have both '--%s' and '%s'") \
                    % (options.info_action, opt))
            options.info_action = new_info_action

        elif arg == "":
            extra.append(opt)
        else:
            extra.extend([arg, opt])

    logging.basicConfig (level = logLevel)

    ret = extra + args

    if options.jobname is not None and len (ret) > 1:
        raise rubber.SyntaxError (_("error: cannot give jobname and have more than one input file"))

    if command_name == RUBBER_PLAIN:
        if len (ret) == 0:
            raise rubber.SyntaxError (_("a file argument is required"))
        if options.clean and options.force:
            raise rubber.Syntaxerror (_("incompatible options: %s and %s") % ("--clean", "--force"))
        if (options.warn_boxes or options.warn_refs or options.warn_misc) \
           and options.clean:
            raise rubber.Syntaxerror (_("incompatible options: %s and %s") % ("--clean", "--warn"))

    elif command_name == RUBBER_PIPE:
        if ret:
            raise SyntaxError (_("rubber-pipe takes no file argument"))

    else: # command_name == RUBBER_INFO
        if len (ret) == 0:
            raise rubber.SyntaxError (_("a file argument is requred"))
        if options.info_action is None:
            options.info_action = "check"

    return options, ret

def prepare_source (filename, command_name, env, options):
    """
    Prepare the dependency node for the main LaTeX run.
    Returns the filename of the main LaTeX source file, which might
    change for various reasons (adding a .tex suffix; preprocessors;
    pipe dumping).
    When this is done, the file must exist on disk, otherwise this
    function must exit(1) or exit(2).
    """
    path = rubber.util.find_resource (filename, suffix=".tex")

    if path is None:
        raise rubber.GenericError (_("Main document not found: '%s'") % filename)

    base, ext = os.path.splitext (path)

    if ext in rubber.converters.literate.literate_preprocessors.keys ():
        src = base + ".tex"
        # FIXME kill src_node
        src_node = rubber.converters.literate.literate_preprocessors [ext] (env.depends, src, path)
        if command_name == RUBBER_PLAIN and not options.clean:
            if not options.unsafe:
                raise rubber.SyntaxError (_("Running external commands requires --unsafe."))
            # Produce the source from its dependency rules, if needed.
            if src_node.make () == rubber.depend.ERROR:
                raise rubber.GenericError (_("Producing the main LaTeX file failed: '%s'") \
                    % src)
    else:
        src = path

    env.final = env.main = rubber.converters.latex.LaTeXDep (env, src, options.jobname)

    return src

def main (command_name):
    assert command_name in (RUBBER_PLAIN, RUBBER_PIPE, RUBBER_INFO)

    try:
        options, args = parse_opts (command_name)

        args = map (os.path.abspath, args)

        if options.place is not None:
            options.place = os.path.abspath(options.place)

        msg.debug (_("This is Rubber version %s.") % rubber.version.version)

        if command_name == RUBBER_PIPE:
            # Generate a temporary source file, and pretend it has
            # been given on the command line.
            args = (prepare_source_pipe (), )

        for src in args:

            msg.debug (_("about to process file '%s'") % src)

            # Go to the appropriate directory
            try:
                if options.place is None:
                    os.chdir (os.path.dirname (src))
                else:
                    os.chdir (options.place)
            except OSError as e:
                raise rubber.GenericError (_("Error changing to working directory: %s") % e.strerror)

            # prepare the source file.  this may require a pre-processing
            # step, or dumping stdin.  thus, the input filename may change.
            # in case of build mode, preprocessors will be run as part of
            # prepare_source.
            env = rubber.environment.Environment ()
            src = prepare_source (src, command_name, env, options)

            # safe mode is off during the prologue
            env.is_in_unsafe_mode_ = True

            if options.include_only is not None:
                env.main.includeonly (options.include_only)

            # at this point, the LaTeX source file must exist; if it is
            # the result of pre-processing, this has happened already.
            # the main LaTeX file is not found via find_file (unlike
            # most other resources) by design:  paths etc may be set up
            # from within via rubber directives, so that wouldn't make a
            # whole lot of sense.
            if not os.path.exists (src):
                raise rubber.GenericError (_("LaTeX source file not found: '%s'") % src)

            env.path.extend (options.texpath)

            saved_vars = env.main.vars.copy ()
            for cmd in options.prologue:
                cmd = rubber.util.parse_line (cmd, env.main.vars)
                env.main.command(cmd[0], cmd[1:], {'file': 'command line'})
            env.main.vars = saved_vars

            # safe mode is enforced for anything that comes from the .tex file
            env.is_in_unsafe_mode_ = options.unsafe

            env.main.parse()

            saved_vars = env.main.vars.copy ()
            for cmd in options.epilogue:
                cmd = rubber.util.parse_line (cmd, env.main.vars)
                env.main.command(cmd[0], cmd[1:], {'file': 'command line'})
            env.main.vars = saved_vars

            if options.compress is not None:
                last_node = env.final
                filename = last_node.products[0]
                if options.compress == 'gzip':
                    import gzip
                    env.final = rubber.converters.compressor.Node (
                        env.depends, gzip.GzipFile, '.gz', filename)
                else:
                    assert options.compress == 'bzip2'
                    import bz2
                    env.final = rubber.converters.compressor.Node (
                        env.depends, bz2.BZ2File, '.bz2', filename)

            if command_name == RUBBER_PIPE:
                # can args [0] be different from src here?
                process_source_pipe (env, args [0], options)
            elif command_name == RUBBER_INFO:
                process_source_info (env, options.info_action, options.short)
            elif options.clean:
                # ex options.clean ()
                for dep in env.final.set.values ():
                    dep.clean ()
            else:
                build (options, RUBBER_PLAIN, env)

    except KeyboardInterrupt:
        msg.warning (_("*** interrupted"))
        sys.exit (1)
    except rubber.SyntaxError as e:
        print (str (e), file=sys.stderr)
        sys.exit (1)
    except rubber.GenericError as e:
        print (str (e), file=sys.stderr)
        sys.exit (2)

def build (options, command_name, env):
    """
    Build the final product.
    """
    assert command_name == RUBBER_PIPE \
            or (command_name == RUBBER_PLAIN and not options.clean)
    srcname = env.main.sources[0]

    if command_name == RUBBER_PLAIN and options.force:
        ret = env.main.make(True)
        if ret != rubber.depend.ERROR and env.final is not env.main:
            ret = env.final.make()
        else:
            # This is a hack for the call to get_errors() below
            # to work when compiling failed when using -f.
            env.final.failed_dep = env.main.failed_dep
    else:
        ret = env.final.make (force = False)

    if ret == rubber.depend.ERROR:
        msg.info(_("There were errors compiling %s.") % srcname)
        number = options.max_errors
        for err in env.final.failed().get_errors():
            if number == 0:
                msg.info(_("More errors."))
                break
            display (options.short, **err)
            number -= 1
        # Ensure a message even with -q.
        raise rubber.GenericError (_("Stopping because of compilation errors."))

    if ret == rubber.depend.UNCHANGED:
        msg.info(_("nothing to be done for %s") % srcname)

    if options.warn_boxes or options.warn_misc or options.warn_refs:
        # FIXME
        log = env.main.log
        if not env.main.parse_log ():
            msg.error(_("cannot read the log file"))
            return 1
        for err in log.parse(boxes=options.warn_boxes,
            refs=options.warn_refs, warnings=options.warn_misc):
            display (options.short, **err)

def display (short, kind, text, **info):
    """
    Print an error or warning message. The argument 'kind' indicates the
    kind of message, among "error", "warning", "abort", the argument
    'text' is the main text of the message, the other arguments provide
    additional information, including the location of the error.
    """
    if kind == "error":
        if text[0:13] == "LaTeX Error: ":
            text = text[13:]
        msg.warning (rubber.util._format (info, text))
        if "code" in info and info["code"] and not short:
            if "macro" in info:
                del info["macro"]
            msg.warning (rubber.util._format (info, _("leading text: ") + info["code"]))
    elif kind == "abort":
        if short:
            m = _("compilation aborted ") + info["why"]
        else:
            m = _("compilation aborted: %s %s") % (text, info["why"])
        msg.warning (rubber.util._format (info, m))
    else:
        assert kind == "warning"
        msg.warning (rubber.util._format (info, text))

full_help_pipe = _("""\
usage: rubber-pipe [options]
available options:
  -b, --bzip2              compress the final document with bzip2
  -c, --command=CMD        run the directive CMD before parsing (see man page)
  -e, --epilogue=CMD       run the directive CMD after parsing
  -z, --gzip               compress the final document
  -h, --help               display this help
      --into=DIR           go to directory DIR before compiling
  -k, --keep               keep the temporary files after compiling
  -n, --maxerr=NUM         display at most NUM errors (default: 10)
  -m, --module=MOD[:OPTS]  use module MOD (with options OPTS)
      --only=SOURCES       only include the specified SOURCES
  -o, --post=MOD[:OPTS]    postprocess with module MOD (with options OPTS)
  -d, --pdf                produce a pdf (synonym for -m pdftex or -o ps2pdf)
  -p, --ps                 process through dvips (synonym for -m dvips)
  -q, --quiet              suppress messages
  -r, --read=FILE          read additional directives from FILE
  -S, --src-specials       enable insertion of source specials
  -s, --short              display errors in a compact form
  -I, --texpath=DIR        add DIR to the search path for LaTeX
  -v, --verbose            increase verbosity
      --version            print version information and exit
""")

def prepare_source_pipe ():
    """
    Dump the standard input in a file, and set up that file
    the same way we would normally process LaTeX sources.
    """

    try:
        # Make a temporary on-disk copy of the standard input,
        # in the current working directory.
        # The name will have the form "rubtmpXXX.tex.
        with tempfile.NamedTemporaryFile (suffix='.tex', prefix='rubtmp', dir='.', delete=False) as srcfile:
            # note the tempfile name so we can remove it later
            pipe_tempfile = srcfile.name
            # copy stdin into the tempfile
            msg.info (_("saving the input in %s") % pipe_tempfile)
            shutil.copyfileobj (sys.stdin.buffer, srcfile)
    except IOError:
        raise rubber.GenericError (_("cannot create temporary file for the main LaTeX source"))

    return pipe_tempfile

def process_source_pipe (env, pipe_tempfile, options):
    """
    Build the document, and dump the result on stdout.
    """
    try:
        build (options, RUBBER_PIPE, env)
        filename = env.final.products[0]
        try:
            # dump the results on standard output
            with open (filename, "rb") as output:
                shutil.copyfileobj (output, sys.stdout.buffer)
        except IOError:
            raise rubber.GenericError (_("error copying the product '%s' to stdout") % filename)
    finally:
        # clean the intermediate files
        if not options.keep_temp:
            for dep in env.final.set.values ():
                dep.clean ()
            if os.path.exists (pipe_tempfile):
                msg.info (_("removing %s") % os.path.relpath (pipe_tempfile))
                os.remove (pipe_tempfile)

full_help_info = _("""\
usage: rubber-info [options] source
available options:
  all options accepted by rubber(1)
actions:
  --boxes     report overfull and underfull boxes
  --check     report errors or warnings (default action)
  --deps      show the target file's dependencies
  --errors    show all errors that occured during compilation
  --help      display this help
  --refs      show the list of undefined references
  --rules     print the dependency rules including intermediate results
  --version   print the program's version and exit
  --warnings  show all LaTeX warnings
""")

def process_source_info (env, act, short):
    if act == "deps":
        deps = [ k for k,n in env.depends.items () if type (n) is rubber.depend.Leaf ]
        print (" ".join (deps))

    elif act == "rules":
        seen = {}
        next = [env.final]
        while len(next) > 0:
            node = next[0]
            next = next[1:]
            if node in seen:
                continue
            seen[node] = None
            if len(node.sources) == 0:
                continue
            print ("\n%s:" % " ".join (node.products))
            print (" ".join (node.sources))
            next.extend(node.source_nodes())

    else:
        # Check for a log file and extract information from it if it exists,
        # accroding to the argument's value.
        log = env.main.log
        if not env.main.parse_log ():
            raise rubber.GenericError (_("Parsing the log file failed"))

        if act == "boxes":
            for err in log.get_boxes():
                display (short, **err)
            else:
                msg.info(_("There is no bad box."))
        elif act == "check":
            finished = False
            for err in log.get_errors ():
                display (short, **err)
                finished = True
            if finished:
                return 0
            msg.info(_("There was no error."))
            for err in log.get_references():
                display (short, **err)
                finished = True
            if finished:
                return 0
            msg.info(_("There is no undefined reference."))
            for err in log.get_warnings():
                display (short, **err)
            else:
                msg.info(_("There is no warning."))
            for err in log.get_boxes ():
                display (short, **err)
            else:
                msg.info(_("There is no bad box."))
        elif act == "errors":
            for err in log.get_errors():
                display (short, **err)
            else:
                msg.info(_("There was no error."))
        elif act == "refs":
            for err in log.get_references():
                display (short, **err)
            else:
                msg.info(_("There is no undefined reference."))
        else:
            assert act == "warnings"
            for err in log.get_warnings ():
                display (short, **err)
            else:
                msg.info(_("There is no warning."))
