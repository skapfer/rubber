"""
This module contains code for handling dependency graphs.
"""
# vim: noet:ts=4

import os, time
from subprocess import Popen
import rubber.util
from rubber.util import _, msg, devnull

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
	def __init__ (self, set, products=[], sources=[]):
		"""
		Initialize the object for a given set of output files and a given set
		of sources. The argument `products' is the list of names for files
		produced by this node, and the argument `sources' is the list of names
		for the dependencies. The node registers itself in the dependency set,
		and if a given depedency is not known in the set, a leaf node is made
		for it.
		"""
		self.set = set
		self.products = []
		self.sources = []
		self.md5_for_source = {}
		# making is the lock guarding against making a node while making it
		self.making = False
		# date: timestamp when this Node was last successfully built.
		# is initialized to the mtime of the most recent product,
		# or to None if a product is missing.
		# when a build succeeds, it is set to time.time(), including fractional
		# seconds. in case building fails, it is set to None.
		self.date = 0  # 1970-01-01 (will be updated in add_product)
		# failed_dep: the Node which caused the build to fail.  can be self
		# if this Node failed to build, or a dependency.
		self.failed_dep = None

		for name in products:
			self.add_product(name)
		for name in sources:
			self.add_source(name)

	def reset_sources (self, names=[]):
		"""
		Redefine the set of produced files for this node.
		"""
		self.sources = []
		for name in names:
			self.add_source(name)

	def add_source (self, name, track_contents=False):
		"""
		Register a new source for this node. If the source is unknown, a leaf
		node is made for it.
		"""
		if not self.set.has_key(name):
			self.set[name] = Leaf(self.set, name)
		if name not in self.sources:
			self.sources.append(name)
		if track_contents:
			# mark as "hash unknown"
			# only for the second build during this rubber run, we want to skip
			# recompiling based on MD5 hashes.  for the first build, only the
			# date counts.
			self.md5_for_source[name] = "UNKNOWN"

	def remove_source (self, name):
		"""
		Remove a source for this node.
		"""
		self.sources.remove (name)
		if self.md5_for_source.has_key (name):
			del self.md5_for_source[name]

	def add_product (self, name):
		"""
		Register a new product for this node.
		"""
		self.set[name] = self
		if name not in self.products:
			self.products.append(name)
		try:
			if self.date is not None:
				self.date = max (os.path.getmtime (name), self.date)
		except OSError:
			# a product is missing, we should_make at least once.
			self.date = None

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

	def should_make (self):
		"""
		Check the dependencies. Return true if this node has to be recompiled,
		i.e. if some dependency is modified. Nothing recursive is done here.
		"""
		if not self.date:
			return True
		for source_name in self.sources:
			source = self.set[source_name]
			# FIXME complain if source has been modified in an unplanned way
			# NB: we ignore the case source.date == None (missing dependency) here.
			# NB2: to be extra correct, equal (disk-precision) timestamps trigger a recompile.
			if source.date is not None and source.date >= self.date:
				if self.md5_for_source.has_key (source_name):
					if self.md5_for_source[source_name] == rubber.util.md5_file (source_name):
						# file contents is identical, ignore the mtime
						continue
					msg.debug(_("while making %s: contents of dependency %s changed, rebuilding") % (self.products[0], source_name), pkg="depend")
					return True
				msg.debug(_("while making %s: timestamp of dependency %s changed, rebuilding") % (self.products[0], source_name), pkg="depend")
				return True
		return False

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
		self.failed_dep = None

		rv = UNCHANGED
		patience = 5
		primary_product = self.products[0]
		msg.debug(_("entering make for %s") % primary_product, pkg="depend")
		while patience > 0:
			# make our sources
			for source_name in self.sources:
				source = self.set[source_name]
				if source.making:
					# cyclic dependency -- drop for now, we will re-visit
					# this would happen while trying to remake the .aux in order to make the .bbl, for example
					msg.debug(_("while making %s: cyclic dependency on %s (pruned)") % (primary_product, source_name), pkg="depend")
					continue
				source_rv = source.make (force)
				if source_rv == ERROR:
					self.making = False
					self.date = None
					self.failed_dep = source.failed_dep
					msg.debug(_("while making %s: dependency %s could not be made") % (primary_product, source_name), pkg="depend")
					return ERROR
				elif source_rv == CHANGED:
					rv = CHANGED

			must_make = force or self.should_make ()
			if not must_make:
				# FIXME convert this to context manager
				self.making = False
				assert self.date is not None
				return rv

			# record MD5 hash of source files as we now actually start the build
			for source_name in self.md5_for_source.keys ():
				self.md5_for_source[source_name] = rubber.util.md5_file (source_name)

			# actually make
			if not self.run ():
				self.making = False
				self.date = None
				self.failed_dep = self
				return ERROR

			self.date = time.time ()
			rv = CHANGED
			force = False

			patience -= 1

		self.making = False
		self.date = None
		self.failed_dep = self
		msg.error(_("while making %s: file contents does not seem to settle") % self.products[0], pkg="depend")
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
		Remove the files produced by this rule and recursively clean all
		dependencies.
		"""
		for file in self.products:
			if os.path.exists(file):
				msg.log(_("removing %s") % file)
				os.unlink(file)
		for source in self.source_nodes():
			source.clean()
		self.date = None

	def leaves (self):
		"""
		Return a list of all source files that are required by this node and
		cannot be built, i.e. the leaves of the dependency tree.
		"""
		if self.sources == []:
			return self.products
		ret = []
		for source in self.source_nodes():
			ret.extend(source.leaves())
		return ret

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
		Node.__init__(self, set, products=[name])

	def make (self, force=False):
		# custom version to cut down on debug messages
		return UNCHANGED if self.run () else ERROR

	def run (self):
		if self.date is not None:
			return True
		# FIXME
		msg.error(_("%r does not exist") % self.products[0], pkg="leaf")
		return False

	def clean (self):
		pass

class Shell (Node):
	"""
	This class specializes Node for generating files using shell commands.
	"""
	def __init__ (self, set, command, products, sources):
		Node.__init__(self, set, products, sources)
		self.command = command
		self.stdout = None

	def run (self):
		msg.progress(_("running: %s") % ' '.join(self.command))
		process = Popen(self.command, stdin=devnull(), stdout=self.stdout)
		if process.wait() != 0:
			msg.error(_("execution of %s failed") % self.command[0])
			return False
		return True

class Pipe (Shell):
	"""
	This class specializes Node for generating files using the stdout of shell commands.
	"""
	def __init__ (self, set, command, products, sources):
		Shell.__init__(self, set, command, products, sources)

	def run (self):
		self.stdout = open(self.products[0], 'w')
		ret = Shell.run(self)
		self.stdout.close()
		return ret
