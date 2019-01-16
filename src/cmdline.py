# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# (c) Sebastian Kapfer, 2015
# vim: noet:ts=4
"""
This is the command line interface for Rubber.
"""

import argparse
import os.path
import sys
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

def parse_opts (command_name):

    class DeprecatedAction (argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            raise rubber.SyntaxError ('obsolete option: ' + option_string)

    if command_name == RUBBER_PLAIN:
        parser = argparse.ArgumentParser (
            description = 'Run TeX until a document is built.')
        parser.add_argument ('source', nargs='+')
        mode = parser.add_mutually_exclusive_group ()
        mode.add_argument ('--clean', action='store_true',
            help='remove produced files instead of compiling')
    elif command_name == RUBBER_PIPE:
        parser = argparse.ArgumentParser (
            description = 'Build a TeX document received on standard input.')
    else: # command_name == RUBBER_INFO
        parser = argparse.ArgumentParser (description = """
            Filter messages from the log created by a previous run of rubber.
            One of the following options must be selected:
            boxes, check (the default), deps, errors,refs, rules or warning.
        """)
        parser.add_argument ('source', nargs='+')
        parser.set_defaults (info_action='check')
        info_action = parser.add_mutually_exclusive_group ()
        info_action.add_argument (
            '--boxes',
            action='store_const', dest='info_action', const='boxes',
            help='report overfull and underfull boxes')
        info_action.add_argument (
            '--check',
            action='store_const', dest='info_action', const='check',
            help='report errors or warnings (default action)')
        info_action.add_argument (
            '--deps',
            action='store_const', dest='info_action', const='deps',
            help="show the target file's dependencies")
        info_action.add_argument (
            '--errors',
            action='store_const', dest='info_action', const='errors',
            help='show all errors that occured during compilation')
        info_action.add_argument (
            '--refs',
            action='store_const', dest='info_action', const='refs',
            help='show the list of undefined references')
        info_action.add_argument (
            '--rules',
            action='store_const', dest='info_action', const='rules',
            help='print the dependency rules including intermediate results')
        info_action.add_argument (
            '--warnings',
            action='store_const', dest='info_action', const='warnings',
            help='show all LaTeX warnings')

    parser.set_defaults (
        epilogue = [],
        place    = '.',
        prologue = [],
    )
    compress = parser.add_mutually_exclusive_group ()
    place    = parser.add_mutually_exclusive_group ()

    # Non-mode options, sorted by short name, else by long name.

    compress.add_argument ('-b', '--bzip2', action='store_const',
        const='bzip2', dest='compress',
        help='compress the final document with bzip2')

    parser.add_argument ('-c', '--command', action='append', dest='prologue',
        metavar='CMD', help='run the directive CMD before parsing')

    class PDFAction (argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            if 'module dvips' in namespace.epilogue:
                namespace.epilogue.append ('module ps2pdf')
            else:
                namespace.prologue.append ('module pdftex')
    parser.add_argument ('-d', '--pdf', action=PDFAction, nargs=0,
        help="shortcut for -c 'module pdftex' or -e 'module ps2pdf'")

    parser.add_argument ('-e', '--epilogue', action='append', metavar='CMD',
        help='run the directive CMD after parsing')

    if command_name == RUBBER_PLAIN:
        mode.add_argument ('-f', '--force', action='store_true',
            help='force at least one compilation')

    if command_name != RUBBER_PIPE:
        place.add_argument ('--inplace', action='store_const', dest='place',
            const=None,
            help='compile the documents from their source directory')

    place.add_argument ('--into', dest='place', metavar='DIR',
        help='go to directory DIR before compiling')

    parser.set_defaults (texpath  = [])
    parser.add_argument ('-I', '--texpath', action='append', metavar='DIR',
        help='add DIR to the search path for LaTeX')

    parser.add_argument ('--jobname',
        help='set the job name for the first target')

    if command_name == RUBBER_PIPE:
        parser.add_argument ('-k', '--keep', action='store_true',
            help='keep the temporary files after compiling')

    parser.add_argument ('-l', '--landscape', nargs=0,
        action=DeprecatedAction,
        help='obsolete option, must not be used')

    class ModuleAction (argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            namespace.prologue.append (
                'module ' + values.replace (':', ' ', 1))
    parser.add_argument ('-m', '--module', action=ModuleAction,
        metavar='MOD[:OPTS]',  help="shortcut for -c 'module MOD OPTS'")

    parser.add_argument ('-n', '--maxerr', type=int, default=10,
        metavar='NUM', help='display at most NUM errors (default %(default)i)')

    class PostAction (argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            namespace.epilogue.append (
                'module ' + values.replace (':', ' ', 1))
    if command_name != RUBBER_INFO:
        parser.add_argument ('-o', '--post', action=PostAction,
            metavar='MOD[:OPTS]', help="shortcut for -e 'module MOD OPTS'")

    parser.add_argument ('--only', metavar='SOURCE[,SOURCE,...]',
        help='only include the specified SOURCES')

    parser.add_argument ('-p', '--ps', action='append_const', dest='epilogue',
        const='module dvips', help="shortcut for -e 'module dvips'")

    parser.add_argument ('-q', '--quiet', action='count',
        help='decrease verbosity (may be repeated)')

    class ReadAction (argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            namespace.prologue.append ('read ' + values)
    parser.add_argument ('-r', '--read', action=ReadAction, metavar='FILE',
        help="shortcut for -c 'read FILE'")

    parser.add_argument ('--readopts', action=DeprecatedAction,
        help='obsolete option, must not be used')

    parser.add_argument ('-s', '--short', action='store_true',
        help='display errors in a compact form')

    parser.add_argument ('-S', '--src-specials', action='append_const',
        dest='prologue', const='set src-specials yes',
        help="shortcut for -c 'set src-specials yes'")

    parser.add_argument ('--synctex', action='append_const', dest='prologue',
        const='synctex', help='shortcut for -c synctex')

    parser.add_argument ('--unsafe', '--shell-escape', action='store_true',
        help='permits the document to run external commands')

    parser.add_argument ('-v', '--verbose', action='count',
        help='increase verbosity (may be repeated)')

    parser.add_argument ('--version', action='version',
        version='%(prog)s ' + rubber.version.version)

    warn_values = ('all', 'boxes', 'misc', 'refs')
    class WarnAction (argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            if option_string == 'all':
                namespace.warn_boxes = True
                namespace.warn_misc  = True
                namespace.warn_refs  = True
            else:
                setattr (namespace, 'warn_' + values, True)
    if command_name != RUBBER_INFO:
        parser.set_defaults (warn_boxes = False,
                             warn_misc  = False,
                             warn_refs  = False)
        parser.add_argument ('-W', '--warn', action=WarnAction,
            metavar='TYPE', choices=warn_values,
            help='report warnings matching TYPE: '   + ','.join (warn_values))

    compress.add_argument ('-z', '--gzip', action='store_const', const='gzip',
        dest='compress', help='compress the final document with gzip')

    args = parser.parse_args ()

    if args.jobname is not None and 1 < len (args.source):
        raise rubber.SyntaxError (_('--jobname requires at most one source'))

    if command_name == RUBBER_PLAIN and args.clean \
       and (args.warn_boxes or args.warn_refs or args.warn_misc):
        raise rubber.Syntaxerror ('incompatible options: --clean and --warn')

    logLevel = logging.WARNING
    if args.verbose: logLevel -= 10*args.verbose
    if args.quiet  : logLevel += 10*args.quiet
    if logging.ERROR < logLevel: logLevel = logging.ERROR
    if logLevel < logging.DEBUG: logLevel = logging.DEBUG
    logging.basicConfig (level = logLevel)

    return args

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
        src_node = rubber.converters.literate.literate_preprocessors [ext] (src, path)
        if command_name == RUBBER_PLAIN and not options.clean:
            if not options.unsafe:
                raise rubber.SyntaxError (_("Running external commands requires --unsafe."))
            # Produce the source from its dependency rules, if needed.
            try:
                src_node.make ()
            except rubber.depend.MakeError as e:
                raise rubber.GenericError (
                    _("Producing the main LaTeX file {} failed: {}")
                    .format (src, e.msg))
    else:
        src = path

    env.final = env.main = rubber.converters.latex.LaTeXDep (env, src, options.jobname)

    return src

def main (command_name):
    assert command_name in (RUBBER_PLAIN, RUBBER_PIPE, RUBBER_INFO)

    try:
        options = parse_opts (command_name)

        msg.debug (_("This is Rubber version %s.") % rubber.version.version)

        if command_name == RUBBER_PIPE:
            # Generate a temporary source file, and pretend it has
            # been given on the command line.
            args = (prepare_source_pipe (), )
        else:
            args = options.source

        if options.place is None: # --inplace
            # Compute all absolute paths before the first chdir.
            args = map (os.path.abspath, args)
        elif options.place != '.': # non default --into
            print ("                       into", options.place)
            # Make arguments relative to the new directory,
            # go there then proceed normally.
            args = map (lambda p:os.path.relpath (p, options.place), args)
            try:
                os.chdir (options.place)
            except OSError as e:
                raise rubber.GenericError \
                    (_("Error changing to %s from --into option: %s") \
                     % (options.place, e.strerror))

        for src in args:

            msg.debug (_("about to process file '%s'") % src)

            if options.place is None: # --inplace
                # Chdir to the absolute path, then keep the base name.
                src_dirname, src = os.path.split (src)
                try:
                    os.chdir (src_dirname)
                except OSError as e:
                    raise rubber.GenericError \
                        (_("Error changing to directory %s for %s: %s")\
                         % (src_dirname, src, e.strerror))

            # prepare the source file.  this may require a pre-processing
            # step, or dumping stdin.  thus, the input filename may change.
            # in case of build mode, preprocessors will be run as part of
            # prepare_source.
            env = rubber.environment.Environment ()
            src = prepare_source (src, command_name, env, options)

            # safe mode is off during the prologue
            env.is_in_unsafe_mode_ = True

            if options.only is not None:
                env.main.includeonly (options.only)

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
                filename = last_node.primary_product ()
                if options.compress == 'gzip':
                    import gzip
                    env.final = rubber.converters.compressor.Node (
                        gzip.GzipFile, '.gz', filename)
                else:
                    assert options.compress == 'bzip2'
                    import bz2
                    env.final = rubber.converters.compressor.Node (
                        bz2.BZ2File, '.bz2', filename)

            if command_name == RUBBER_PIPE:
                process_source_pipe (env, src, options)
            elif command_name == RUBBER_INFO:
                process_source_info (env, options.info_action, options.short)
            elif options.clean:
                for node in env.final.all_producers ():
                    node.clean ()
                cache_path = env.main.basename ('.rubbercache')
                if os.path.exists (cache_path):
                    msg.debug (_("removing %s"), cache_path)
                    os.remove (cache_path)
            else:
                build (options, RUBBER_PLAIN, env)

        if (command_name == RUBBER_PLAIN and options.clean) \
           or (command_name == RUBBER_PIPE and not options.keep):
            rubber.depend.clean_all_products ()

    except KeyboardInterrupt:
        msg.warning (_("*** interrupted"))
        sys.exit (1)
    except rubber.SyntaxError as e:
        print ('error: ' + str (e), file=sys.stderr)
        sys.exit (1)
    except rubber.GenericError as e:
        print ('error: ' + str (e), file=sys.stderr)
        sys.exit (2)

def build (options, command_name, env):
    """
    Build the final product.
    """
    assert command_name == RUBBER_PIPE \
            or (command_name == RUBBER_PLAIN and not options.clean)

    cache_path = env.main.basename ('.rubbercache')
    if os.path.exists (cache_path):
        if command_name == RUBBER_PLAIN and options.force:
            msg.debug (_('Ignoring cache file if any because of --force.'))
        else:
            rubber.depend.load_cache (cache_path)

    try:
        if command_name == RUBBER_PLAIN and options.force:
            ret = env.main.make ()
            if env.final is not env.main:
                ret = env.final.make () or ret
        else:
            ret = env.final.make ()
    except rubber.depend.MakeError as e:
        msg.info (_("There were errors compiling %s: %s."),
                  env.main.source (), e.msg)
        number = options.maxerr
        for err in e.errors:
            if number == 0:
                msg.info(_("More errors."))
                break
            display (options.short, **err)
            number -= 1
        # Ensure a message even with -q.
        raise rubber.GenericError (_("Stopping because of compilation errors."))

    if ret:
        rubber.depend.save_cache (cache_path, env.final)
    else:
        msg.info (_("nothing to be done for %s"), env.main.source ())

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

def prepare_source_pipe ():
    """
    Dump the standard input in a file, and set up that file
    the same way we would normally process LaTeX sources.
    """

    # FIXME: with a better program structure, the context manager
    # should remove the input file.

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
        filename = env.final.primary_product ()
        try:
            # dump the results on standard output
            with open (filename, "rb") as output:
                shutil.copyfileobj (output, sys.stdout.buffer)
        except IOError:
            raise rubber.GenericError (_("error copying the product '%s' to stdout") % filename)
    finally:
        # clean the intermediate files
        if not options.keep:
            for node in env.final.all_producers ():
                node.clean ()
            cache_path = env.main.basename ('.rubbercache')
            if os.path.exists (cache_path):
                msg.debug (_("removing %s"), cache_path)
                os.remove (cache_path)
            if os.path.exists (pipe_tempfile):
                msg.info (_("removing %s"), pipe_tempfile)
                os.remove (pipe_tempfile)

def process_source_info (env, act, short):
    if act == "deps":
        print (" ".join (env.final.all_leaves ()))

    elif act == "rules":
        for node in env.final.all_producers ():
            print ("\n%s:" % " ".join (node.products ()))
            print (" ".join (node.sources))

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
