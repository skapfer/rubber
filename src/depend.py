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
    def __init__ (self, set):
        """
        The node registers itself in the dependency set,
        and if a given depedency is not known in the set, a leaf node is made
        for it.
        """
        self.set = set
        self.products = []
        self.sources = []
        # A snapshot of each source as they were used during last
        # successful build, or None if no build has been attempted yet.
        self.snapshots = None
        # making is the lock guarding against making a node while making it
        self.making = False
        self.products_exist = False
        # failed_dep: the Node which caused the build to fail.  can be self
        # if this Node failed to build, or a dependency.
        self.failed_dep = None

    def add_source (self, name):
        """
        Register a new source for this node. If the source is unknown, a leaf
        node is made for it.
        """
        # The same source may be inserted many times in the same
        # document (an image containing a logo for example).
        if name in self.sources:
            assert name in self.set
        else:
            # The same file may be a source for various recipes.
            if name not in self.set:
                self.set[name] = Leaf(self.set, name)
            self.sources.append (name)

    def remove_source (self, name):
        """
        Remove a source for this node.
        """
        self.sources.remove (name)
        # FIXME: remove from dependency set?

    def add_product (self, name):
        """
        Register a new product for this node.
        """
        self.set[name] = self
        if name in self.products:
            raise rubber.GenericError ('already a product named ' + name)
        self.products.append(name)

    def replace_primary_product (self, name):
        if name != self.products [0]:
            if name in self.products:
                raise rubber.GenericError ('already a product named ' + name)

            del self.set [self.products [0]]
            self.set [name] = self
            self.products [0] = name

    def source_nodes (self):
        """
        Return the list of nodes for the sources of this node.
        """
        return [self.set[name] for name in self.sources]

    def is_leaf (self):
        """
        Returns True if this node is a leaf node.
        """
        return self.sources == []

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
        primary_product = self.products[0]
        msg.debug(_("make %s -> %r") % (primary_product, self.sources))
        for patience in range (5):
            # make our sources
            for source_name in self.sources:
                source = self.set[source_name]
                if source.making:
                    # cyclic dependency -- drop for now, we will re-visit
                    # this would happen while trying to remake the .aux in order to make the .bbl, for example
                    msg.debug(_("while making %s: cyclic dependency on %s (pruned)") % (primary_product, source_name))
                    continue
                source_rv = source.make (force)
                if source_rv == ERROR:
                    self.failed_dep = source.failed_dep
                    msg.debug(_("while making %s: dependency %s could not be made") % (primary_product, source_name))
                    return ERROR
                elif source_rv == CHANGED:
                    rv = CHANGED

            if force:
                msg.debug (_("while making %s: --force given"), primary_product)
            elif self.snapshots is None:
                msg.debug (_("while making %s: first attempt, building"),
                           primary_product)
            elif not self.products_exist:
                msg.debug (_("while making %s: product missing, building"),
                           primary_product)
            else:
                for i in range (len (self.sources)):
                    source_name = self.sources [i]
                    source = self.set [source_name]
                    # NB: we ignore this case (missing dependency)
                    if not source.products_exist:
                        msg.debug (_("Not rebuilding %s from missing %s"),
                                   primary_product, source_name)
                    elif self.snapshots is None \
                         or self.snapshots [i] != rubber.contents.contents (source_name):
                        msg.debug (_("Rebuilding %s from outdated %s"),
                                   primary_product, source_name)
                        break
                    else:
                        msg.debug (_("Not rebuilding %s from unchanged %s"),
                                   primary_product, source_name)
                else:
                    return rv

            # record snapshots of sources as we now actually start the build
            self.snapshots = tuple (map (rubber.contents.contents, self.sources))

            # actually make
            if not self.run ():
                self.failed_dep = self
                return ERROR

            self.products_exist = True
            rv = CHANGED
            force = False

        self.failed_dep = self
        msg.error(_("while making %s: file contents does not seem to settle") % self.products[0])
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
            if os.path.exists (file):
                msg.info (_("removing %s") % os.path.relpath (file))
                os.remove (file)
        self.products_exist = False

class Leaf (Node):
    """
    This class specializes Node for leaf nodes, i.e. source files with no
    dependencies.
    """
    def __init__ (self, set, name):
        """
        Initialize the node. The argument of this method are the dependency
        set and the file name.
        """
        super (Leaf, self).__init__(set)
        self.add_product (name)

    def real_make (self, force):
        # custom version to cut down on debug messages
        if not self.run ():
            self.failed_dep = self
            return ERROR
        else:
            return UNCHANGED

    def run (self):
        result = self.snapshots is None or self.products_exist
        if not result:
            msg.error(_("%r does not exist") % self.products[0])
        return result

    def clean (self):
        pass

class Shell (Node):
    """
    This class specializes Node for generating files using shell commands.
    """
    def __init__ (self, set, command):
        super (Shell, self).__init__ (set)
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
    def __init__ (self, set, command, product):
        super (Pipe, self).__init__(set, command)
        self.add_product (product)

    def run (self):
        self.stdout = open(self.products[0], 'bw')
        ret = super (Pipe, self).run ()
        self.stdout.close()
        return ret
