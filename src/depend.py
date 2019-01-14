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

# constants for the return value of Node.make:

ERROR = 0
UNCHANGED = 1
CHANGED = 2

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
                    f.write (node.sources [i].path ())
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
            node = rubber.contents.factory (product).producer ()
            if node is None:
                msg.debug (_('%s: no such recipe anymore') % product)
            elif list (s.path () for s in node.sources) != sources:
                msg.debug (_('%s: depends on %s not anymore on %s'), product,
                     " ".join (s.path () for s in node.sources),
                     " ".join (sources))
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
        self.products = []
        # All prerequisites for this recipe. Elements are instances
        # returned by rubber.contents.factory. A None value for the
        # producer means a leaf node.
        self.sources = []
        # A snapshot of each source as they were used during last
        # successful build, or None if no build has been attempted
        # yet.  The order in the list is the one in self.sources,
        # which does not change during build.
        self.snapshots = None
        # making is the lock guarding against making a node while making it
        self.making = False
        # failed_dep: the Node which caused the build to fail.  can be self
        # if this Node failed to build, or a dependency.
        self.failed_dep = None

    # TODO: once this works and noone outside this files use the
    # dependency set, replace it with a more efficient structure: each
    # node can record once and for all whether it causes a circular
    # dependency or not at creation.
    def all_producers (self):
        seen = set ()
        def rec (node):
            seen.add (node)
            # print ("            yielding ", node)
            yield node
            for source in node.sources:
                child = source.producer ()
                if child is not None  and child not in seen:
                    # print ("            yielding from ", source.path (), child)
                    yield from rec (child)
                # else:
                #     print ("            skipping leaf ", source.path ())
        yield from rec (self)

    def add_source (self, name):
        """
        Register a new source for this node. If the source is unknown, a leaf
        node is made for it.
        """
        # Do nothing when the name is already listed.
        # The same source may be inserted many times in the same
        # document (an image containing a logo for example).
        s = rubber.contents.factory (name)
        if s not in self.sources:
            self.sources.append (s)

    def remove_source (self, name):
        """
        Remove a source for this node.
        """
        # Fail if the name is not listed.
        self.sources.remove (rubber.contents.factory (name))

    def add_product (self, name):
        """
        Register a new product for this node.
        """
        f = rubber.contents.factory (name)
        assert f not in self.products
        f.set_producer (self)
        self.products.append (f)

    def primary_product (self):
        return self.products [0].path ()

    def make (self):
        """
        Make the destination file. This recursively makes all dependencies,
        then compiles the target if dependencies were modified. The return
        value is one of the following:
        - ERROR means that the process failed somewhere (in this node or in
          one of its dependencies)
        - UNCHANGED means that nothing had to be done
        - CHANGED means that something was recompiled (therefore nodes that
          depend on this one might have to be remade)
          This is mainly for diagnostics to the user, rubber no longer makes
          build decisions based on this value - proved to be error-prone.
        """
        # catch if cyclic dependencies have not been detected properly
        assert not self.making
        self.making = True
        rv = self.real_make ()
        self.making = False
        if rv == ERROR:
            assert self.failed_dep is not None
        else:
            assert self.snapshots is not None
            self.failed_dep = None
        return rv

    def real_make (self):
        rv = UNCHANGED
        msg.debug (_("making %s from %s"),
                   " ".join (s.path () for s in self.products),
                   " ".join (s.path () for s in self.sources))
        for patience in range (5):
            # make our sources
            for source in self.sources:
                if source.producer () is None:
                    msg.debug (_("while making %s: %s is a leaf dependency"),
                               self.primary_product (), source.path ())
                    continue
                if source.producer ().making:
                    # cyclic dependency -- drop for now, we will re-visit
                    # this would happen while trying to remake the .aux in order to make the .bbl, for example
                    msg.debug (_("while making %s: cyclic dependency on %s (pruned)"),
                               self.primary_product (), source.path ())
                    continue
                source_rv = source.producer ().make ()
                if source_rv == ERROR:
                    self.failed_dep = source.producer ().failed_dep
                    msg.debug (_("while making %s: dependency %s could not be made"),
                               self.primary_product (), source.path ())
                    return ERROR
                elif source_rv == CHANGED:
                    rv = CHANGED

            if self.snapshots is None:
                msg.debug (_("while making %s: first attempt or --force given, building"),
                           self.primary_product ())
                self.snapshots = tuple (s.snapshot () for s in self.sources)
            else:
                # There has already been a successful build.
                for i in range (len (self.sources)):
                    source = self.sources [i]
                    if self.snapshots [i] != source.snapshot ():
                        msg.debug (_("Rebuilding %s from outdated %s"),
                                   self.primary_product (), source.path ())
                        break
                    else:
                        msg.debug (_("Not rebuilding %s from unchanged %s"),
                                   self.primary_product (), source.path ())
                else:
                    msg.debug (_("No reason to rebuild %s."),
                               self.primary_product ())
                    return rv
                msg.debug (_("Updating snapshots for %s"), self.primary_product ())
                self.snapshots = tuple (s.snapshot () for s in self.sources)

            if (not isinstance (self, rubber.converters.latex.LaTeXDep)) \
               and not all (os.path.exists (s.path ()) for s in self.sources):
                msg.info (_("input files for %s do not yet exist, deferring"),
                          self.primary_product ())

            elif not self.run ():
                self.failed_dep = self
                self.snapshots = None
                return ERROR

            rv = CHANGED
            force = False

        self.failed_dep = self
        msg.error (_("while making %s: file contents does not seem to settle"),
                   self.primary_product ())
        return ERROR

    def run (self):
        """
        This method is called when a node has to be (re)built. It is supposed
        to rebuild the files of this node, returning true on success and false
        on failure. It must be redefined by derived classes.
        """
        return False

    def failed (self):
        """
        Return a reference to the node that caused the failure of the last
        call to 'make'. If there was no failure, return None.
        """
        return self.failed_dep

    def get_errors (self):
        """
        Report the errors that caused the failure of the last call to run, as
        an iterable object.
        """
        return []

    def clean (self):
        """
        Remove the products of this recipe and of recursive dependencies.

                Each override should start with
                super (class, self).clean ()
        """
        for product in self.products:
            path = product.path ()
            if os.path.exists (path):
                msg.info (_("removing %s"), path)
                os.remove (path)

        assert not self.making
        self.making = True
        for source in self.sources:
            producer = source.producer ()
            if producer is not None and not producer.making:
                producer.clean ()
        self.making = False

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
