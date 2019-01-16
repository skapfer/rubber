# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006
# vim:noet:ts=4
"""
This module contains utility functions and classes used by the main system and
by the modules for various tasks.
"""

import os.path, stat
import errno
import imp
import logging
msg = logging.getLogger (__name__)
import re
from string import whitespace
import subprocess
import sys

#-- Message writers --{{{1

# The function `_' is defined here to prepare for internationalization.
def _ (txt): return txt

def _format (where, text):
    """
    Format the given text into a proper error message, with file and line
    information in the standard format. Position information is taken from
    the dictionary given as first argument.
    """
    if where is None or where == {}:
        return text

    if "file" in where and where["file"] is not None:
        pos = where ["file"]
        if "line" in where and where["line"]:
            pos = "%s:%d" % (pos, int(where["line"]))
            if "last" in where:
                if where["last"] != where["line"]:
                    pos = "%s-%d" % (pos, int(where["last"]))
        pos = pos + ": "
    else:
        pos = ""
    if "macro" in where:
        text = "%s (in macro %s)" % (text, where["macro"])
    if "page" in where:
        text = "%s (page %d)" % (text, int(where["page"]))
    if "pkg" in where:
        text = "[%s] %s" % (where["pkg"], text)
    return pos + text

#-- Keyval parsing --{{{1

re_keyval = re.compile("\
[ ,]*\
(?P<key>[^ \t\n{}=,]+)\
([ \n\t]*=[ \n\t]*\
(?P<val>({|[^{},]*)))?")

def parse_keyval (str):
    """
    Parse a list of 'key=value' pairs, with the syntax used in LaTeX's
    standard 'keyval' package. The value returned is simply a dictionary that
    contains all definitions found in the string. For keys without a value,
    the dictionary associates the value None.
    If str is None, consider it as empty.
    """
    dict = {}
    while str:
        m = re_keyval.match(str)
        if not m:
            break
        d = m.groupdict()
        str = str[m.end():]
        if not d["val"]:
            dict[d["key"]] = None
        elif d["val"] == '{':
            val, str = match_brace(str)
            dict[d["key"]] = val
        else:
            dict[d["key"]] = d["val"].strip()
    return dict

def match_brace (str):
    """
    Split the string at the first closing brace such that the extracted prefix
    is balanced with respect to braces. The return value is a pair. If the
    adequate closing brace is found, the pair contains the prefix before the
    brace and the suffix after the brace (not containing the brace). If no
    adequate brace is found, return the whole string as prefix and an empty
    string as suffix.
    """
    level = 0
    for pos in range(0, len(str)):
        if str[pos] == '{':
            level = level + 1
        elif str[pos] == '}':
            level = level - 1
            if level == -1:
                return (str[:pos], str[pos+1:])
    return (str, "")


#-- Checking for program availability --{{{1

checked_progs = {}

def prog_available (prog):
    """
    Test whether the specified program is available in the current path, and
    return its actual path if it is found, or None.
    """
    pathsep = ";" if os.name == "nt" else ":"
    fileext = ".exe" if os.name == "nt" else ""
    if prog in checked_progs:
        return checked_progs[prog]
    for path in os.getenv("PATH").split(pathsep):
        file = os.path.join(path, prog) + fileext
        if os.path.exists(file):
            st = os.stat(file)
            if stat.S_ISREG(st.st_mode) and (st.st_mode & 0o111):
                checked_progs[prog] = file
                return file
    checked_progs[prog] = None
    return None

#-- Parsing commands --{{{1

re_variable = re.compile("(?P<name>[a-zA-Z]+)")

def parse_line (line, dict):
    """
    Decompose a string into a list of elements. The elements are separated by
    spaces, single and double quotes allow escaping of spaces (and quotes).
    Elements can contain variable references with the syntax '$VAR' (with only
    letters in the name) or '${VAR}'.

    If the argument 'dict' is defined, it is considered as a hash containing
    the values of the variables. If it is None, elements with variables are
    replaced by sequences of litteral strings or names, as follows:
        parse_line(" foo  bar${xy}quux toto  ")
            --> ["foo", ["'bar", "$xy", "'quux"], "toto"]
    """
    elems = []
    i = 0
    size = len(line)
    while i < size:
        while i < size and line[i] in whitespace: i = i+1
        if i == size: break

        open = 0    # which quote is open
        arg = ""    # the current argument, so far
        if not dict: composed = None    # the current composed argument

        while i < size:
            c = line[i]

            # Open or close quotes.

            if c in '\'\"':
                if open == c: open = 0
                elif open: arg = arg + c
                else: open = c

            # '$' introduces a variable name, except within single quotes.

            elif c == '$' and open != "'":

                # Make the argument composed, if relevant.

                if not dict:
                    if not composed: composed = []
                    if arg != "": composed.append("'" + arg)
                    arg = ""

                # Parse the variable name.

                if i+1 < size and line[i+1] == '{':
                    end = line.find('}', i+2)
                    if end < 0:
                        name = line[i+2:]
                        i = size
                    else:
                        name = line[i+2:end]
                        i = end + 1
                else:
                    m = re_variable.match(line, i+1)
                    if m:
                        name = m.group("name")
                        i = m.end()
                    else:
                        name = ""
                        i = i+1

                # Append the variable or its name.

                if dict:
                    if name in dict:
                        arg = arg + str(dict[name])
                    elif name in ('cwd', 'base', 'ext', 'path', 'latex', 'program', 'engine', 'file', 'line', ):
                        msg.error (_ ('Obsolete variable: '+ name))
                    elif name in ('graphics_suffixes', 'src-specials', 'logfile_limit', ):
                        msg.error (_ ('Write-only variable: '+ name))
                    else:
                        msg.error (_ ('Unknown variable: '+ name))

                else:
                    composed.append("$" + name)
                continue

            # Handle spaces.

            elif c in whitespace:
                if open: arg = arg + c
                else: break
            else:
                arg = arg + c
            i = i+1

        # Append the new argument.

        if dict or not composed:
            elems.append(arg)
        else:
            if arg != "": composed.append("'" + arg)
            elems.append(composed)

    return elems

def explode_path (name = "PATH"):
    """
    Parse an environment variable into a list of paths, and return it as an array.
    """
    path = os.getenv (name)
    if path is not None:
        return path.split (":")
    else:
        return []

def find_resource (name, suffix = "", paths = []):
    """
    find the indicated file, mimicking what latex would do:
    tries adding a suffix such as ".bib", or looking in the specified paths.
    if unsuccessful, returns None.
    """
    name = name.strip ()

    if os.path.exists (name):
        return name
    elif suffix != "" and os.path.exists (name + suffix):
        return name + suffix

    for path in paths:
        fullname = os.path.join (path, name)
        if os.path.exists (fullname):
            return fullname
        elif suffix != "" and os.path.exists (fullname + suffix):
            return fullname + suffix

    return None

def execute (prog, env={}, pwd=None, out=None):
    """
    Silently execute an external program. The `prog' argument is the list
    of arguments for the program, `prog[0]' is the program name. The `env'
    argument is a dictionary with definitions that should be added to the
    environment when running the program. The standard output is passed
    line by line to the `out' function (or discarded by default).
    """
    msg.info(_("executing: %s") % " ".join (prog))
    if pwd:
        msg.debug(_("  in directory %s") % pwd)
    if env != {}:
        msg.debug(_("  with environment: %r") % env)

    progname = prog_available(prog[0])
    if not progname:
        msg.error(_("%s not found") % prog[0])
        return 1

    penv = os.environ.copy()
    for (key,val) in env.items():
        penv[key] = val

    process = subprocess.Popen(prog,
        executable = progname,
        env = penv,
        cwd = pwd,
        stdin = subprocess.DEVNULL,
        stdout = subprocess.PIPE,
        stderr = None)

    if out is not None:
        for line in process.stdout:
            out(line)
    else:
        process.stdout.readlines()

    ret = process.wait()
    msg.debug(_("process %d (%s) returned %d") % (process.pid, prog[0], ret))
    return ret
