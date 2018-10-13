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
        self.sources = set ()
        # A snapshot of each source as they were used during last
        # successful build, or None if no build has been attempted
        # yet.  The order in the list is the one in self.sources,
        # which does not change during build.
        self.snapshots = None
        # making is the lock guarding against making a node while making it
        self.making = False
        self.products_exist = False
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
        self.sources.add (rubber.contents.factory (name))

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

    def make (self, force=False):
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
        If the optional argument 'force' is true, then the method 'run' is
        called unless an error occurred in dependencies, and in this case
        UNCHANGED cannot be returned.
        """
        # catch if cyclic dependencies have not been detected properly
        assert not self.making
        self.making = True
        rv = self.real_make (force)
        self.making = False
        if rv == ERROR:
            self.products_exist = False
            assert self.failed_dep is not None
        else:
            assert self.products_exist or self.snapshots is None
            self.failed_dep = None
        return rv

    def real_make (self, force):
        rv = UNCHANGED
        msg.debug (_("making %s from %s"),
                   " ".join (s.path () for s in self.products),
                   " ".join (s.path () for s in self.sources))
        for patience in range (5):
            # make our sources
            for source in self.sources:
                if source.producer () is None:
                    continue
                if source.producer ().making:
                    # cyclic dependency -- drop for now, we will re-visit
                    # this would happen while trying to remake the .aux in order to make the .bbl, for example
                    msg.debug (_("while making %s: cyclic dependency on %s (pruned)"),
                               self.primary_product (), source.path ())
                    continue
                source_rv = source.producer ().make (force)
                if source_rv == ERROR:
                    self.failed_dep = source.producer ().failed_dep
                    msg.debug (_("while making %s: dependency %s could not be made"),
                               self.primary_product (), source.path ())
                    return ERROR
                elif source_rv == CHANGED:
                    rv = CHANGED

            if force:
                msg.debug (_("while making %s: --force given"),
                           self.primary_product ())
            elif self.snapshots is None:
                msg.debug (_("while making %s: first attempt, building"),
                           self.primary_product ())
            elif not self.products_exist:
                msg.debug (_("while making %s: product missing, building"),
                           self.primary_product ())
            else:
                i = 0
                for source in self.sources:
                    # NB: we ignore this case (missing dependency)
                    if source.producer () is not None \
                       and not source.producer ().products_exist:
                        msg.debug (_("Not rebuilding %s from missing %s"),
                                   self.primary_product (), source.path ())
                    elif self.snapshots is None:
                        msg.info (_("First build attempt for %s"),
                                  self.primary_product ())
                        break
                    elif self.snapshots [i] != source.snapshot ():
                        msg.debug (_("Rebuilding %s from outdated %s"),
                                   self.primary_product (), source.path ())
                        break
                    else:
                        msg.debug (_("Not rebuilding %s from unchanged %s"),
                                   self.primary_product (), source.path ())
                    i = i + 1
                else:
                    msg.debug (_("No reason to rebuild %s."),
                               self.primary_product ())
                    return rv

            if self.snapshots is None:
                msg.debug (_("Creating snapshots for %s"), " ".join (s.path () for s in self.sources))
            else:
                msg.debug (_("Updating snapshots for %s"), " ".join (s.path () for s in self.sources))
            # record snapshots of sources as we now actually start the build
            self.snapshots = tuple (s.snapshot () for s in self.sources)

            if (not isinstance (self, rubber.converters.latex.LaTeXDep)) \
               and not all (os.path.exists (s.path ()) for s in self.sources):
                msg.info (_("input files for %s do not yet exist, deferring"),
                          self.primary_product ())
            elif not self.run ():
                self.failed_dep = self
                return ERROR

            self.products_exist = True
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
        Remove the files produced by this rule.  Note that cleaning is not
        done recursively; rather, all dependency nodes are cleaned in no
        particular order (see cmdline.py / cmd_pipe.py)

                Each override should start with
                super (class, self).clean ()
        """
        for file in self.products:
            if os.path.exists (file.path ()):
                msg.info (_("removing %s"), file.path ())
                os.remove (file.path ())
        self.products_exist = False

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
