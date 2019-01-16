"""
This module contains code for handling dependency graphs.
"""
# vim: noet:ts=4

import logging
msg = logging.getLogger (__name__)
import os.path
import subprocess
import rubber.contents
from rubber.util import _

class MakeError (Exception):
    def __init__ (self, msg, errors):
        super (MakeError, self).__init__ (msg)
        self.msg    = msg
        self.errors = errors

# Dictionnary allowing to find a Node by one of its products.
# It should not be used outside this module.
_producer = {}

def clean_all_products ():
    """Clean all products of all recipes."""
    for path in _producer:
        if os.path.exists (path):
            msg.info (_("removing %s"), path)
            os.remove (path)

def save_cache (cache_path, final):
    msg.debug (_('Creating or overwriting cache file %s') % cache_path)
    with open (cache_path, 'tw') as f:
        for node in final.all_producers ():
            if node.snapshots is not None:
                f.write (node.primary_product ())
                f.write ('\n')
                for i in range (len (node.sources)):
                    f.write ('  ')
                    f.write (rubber.contents.cs2str (node.snapshots [i]))
                    f.write (' ')
                    f.write (node.sources [i])
                    f.write ('\n')

def load_cache (cache_path):
    msg.debug (_('Reading external cache file %s') % cache_path)
    with open (cache_path) as f:
        line = f.readline ()
        while line:
            product = line [:-1]
            sources = []
            snapshots = []
            while True:
                line = f.readline ()
                if not line.startswith ('  '): # Including end of file.
                    break
                limit = 2 + rubber.contents.cs_str_len
                snapshots.append (rubber.contents.str2cs (line [2:limit]))
                sources.append (line [limit + 1:-1])
            try:
                node = _producer [product]
            except KeyError:
                msg.debug (_('%s: no such recipe anymore') % product)
            else:
              if node.sources != sources:
                msg.debug (_('%s: depends on %s not anymore on %s'), product,
                    " ".join (node.sources), " ".join (sources))
              elif node.snapshots is not None:
                # FIXME: this should not happen. See cweb-latex test.
                msg.debug (_('%s: rebuilt before cache read'), product)
              else:
                msg.debug (_('%s: using cached checksums'), product)
                node.snapshots = snapshots

class Node (object):
    """
    This is the base class to represent dependency nodes. It provides the base
    functionality of date checking and recursive making, supposing the
    existence of a method `run()' in the object.
    """
    def __init__ (self):
        """
        The node registers itself in the dependency set,
        and if a given depedency is not known in the set, a leaf node is made
        for it.
        """
        self.product = None
        # All prerequisites for this recipe.
        self.sources = []
        # A snapshot of each source as they were used during last
        # successful build, or None if no build has been attempted
        # yet.  The order in the list is the one in self.sources,
        # which does not change during build.
        self.snapshots = None
        # making is the lock guarding against making a node while making it
        self.making = False

    def all_producers (self):
        def rec (node):
            if not node.making:
                node.making = True
                try:
                    yield node
                    for source in node.sources:
                        try:
                            child = _producer [source]
                        except KeyError:
                            pass
                        else:
                            yield from rec (child)
                finally:
                    self.making = False
        yield from rec (self)

    def all_leaves (self):
        """Show sources that are not produced."""
        # We need to build a set in order to remove duplicates.
        result = set ()
        def rec (node):
            if not node.making:
                node.making = True
                try:
                    for source in node.sources:
                        if source in _producer:
                            rec (_producer [source])
                        else:
                            result.add (source)
                finally:
                    self.making = False
        rec (self)
        return result

    def add_source (self, name):
        """
        Register a new source for this node. If the source is unknown, a leaf
        node is made for it.
        """
        # Do nothing when the name is already listed.
        # The same source may be inserted many times in the same
        # document (an image containing a logo for example).
        if name not in self.sources:
            self.sources.append (name)

    def remove_source (self, name):
        """
        Remove a source for this node.
        """
        # Fail if the name is not listed.
        self.sources.remove (name)

    def products (self):
        """An iterable with all all products for this recipe.
        This function is not efficient, but called only once by
        cmdline.py with a specific command-line option."""
        return (key for key, value in _producer.items () if value is self)

    def add_product (self, name):
        """
        Register a new product for this node.
        """
        # TODO: why does this break? assert name not in _producer, name
        _producer [name] = self
        if self.product is None:
            self.product = name

    def primary_product (self):
        return self.product

    def replace_product (self, name):
        """Trick for latex.py"""
        # TODO: why does this break? assert name not in _producer, name
        del _producer [self.product]
        self.product = name
        _producer [name] = self

    def make (self):
        """
        Make the destination file. This recursively makes all dependencies,
        then compiles the target if dependencies were modified. The return
        value is
        - False when nothing had to be done
        - True when something was recompiled (among all dependencies)
        MakeError is raised in case of error.
        """
        # The recurrence is similar to all_producers, except that we
        # try each compilations a few times.

        pp = self.primary_product ()

        if self.making:
            msg.debug (_("%s: cyclic dependency, pruning"), pp)
            return False

        rv = False
        self.making = True
        try:
            for patience in range (5):
                msg.debug (_('%s: made from %s   attempt %i'),
                           self.product, ','.join (self.sources),
                           patience)

                # make our sources
                for source in self.sources:
                    try:
                        dep = _producer [source]
                    except KeyError:
                        msg.debug (_("%s: needs %s, leaf"), pp, source)
                    else:
                        msg.debug (_("%s: needs %s, making %s"), pp, source,
                                   dep.primary_product ())
                        rv = dep.make () or rv

                # Once all dependent recipes have been run, check the
                # state of the sources on disk.
                snapshots = tuple (map (rubber.contents.snapshot, self.sources))

                missing = ','.join (
                    self.sources [i] for i in range (len (snapshots))
                    if snapshots [i] == rubber.contents.NO_SUCH_FILE)
                if missing:
                    if isinstance (self, rubber.converters.latex.LaTeXDep) \
                       and self.snapshots is None \
                       and patience == 0:
                        msg.debug (_("%s: missing %s, but first LaTeX run"), pp, missing)
                    else:
                        msg.debug (_("%s: missing %s, pruning"), pp, missing)
                        return rv

                if self.snapshots is None:
                    msg.debug (_("%s: first attempt or --force, building"), pp)
                else:
                    # There has already been a successful build.
                    changed = ','.join (
                        self.sources [i] for i in range (len (snapshots))
                        if self.snapshots [i] != snapshots [i])
                    if not changed:
                        msg.debug (_("%s: sources unchanged since last build"), pp)
                        return rv
                    msg.debug (_("%s: some sources changed: %s"), pp, changed)

                if not self.run ():
                    raise MakeError (_("Recipe for {} failed").format (pp),
                                     self.get_errors ())

                # Build was successful.
                self.snapshots = snapshots
                rv = True

            # Patience exhausted.
            raise MakeError (_("Contents of {} do not settle").format (pp),
                             self.get_errors ())

        finally:
            self.making = False

    def run (self):
        """
        This method is called when a node has to be (re)built. It is supposed
        to rebuild the files of this node, returning true on success and false
        on failure. It must be redefined by derived classes.
        """
        return False

    def get_errors (self):
        """
        Report the errors that caused the failure of the last call to run, as
        an iterable object.
        """
        return []

    def clean (self):
        """
        Remove additional files for this recipe.
        Nothing recursive happens here.
        Files registered as products are removed by rubber.clean ().
        """

class Shell (Node):
    """
    This class specializes Node for generating files using shell commands.
    """
    def __init__ (self, command):
        super ().__init__ ()
        self.command = command
        self.stdout = None

    def run (self):
        msg.info(_("running: %s") % ' '.join(self.command))
        process = subprocess.Popen (self.command,
            stdin=subprocess.DEVNULL,
            stdout=self.stdout)
        if process.wait() != 0:
            msg.error(_("execution of %s failed") % self.command[0])
            return False
        return True

class Pipe (Shell):
    """
    This class specializes Node for generating files using the stdout of shell commands.
    The 'product' will receive the stdout of 'command'.
    """
    def __init__ (self, command, product):
        super ().__init__ (command)
        self.add_product (product)

    def run (self):
        with open (self.primary_product (), 'bw') as self.stdout:
            ret = super (Pipe, self).run ()
        return ret
