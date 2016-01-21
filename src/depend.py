"""
This module contains code for handling dependency graphs.
"""
# vim: noet:ts=4

import os, time
from subprocess import Popen
import rubber.util
from rubber.util import _, msg, devnull

class BuildError (Exception):
	"""
	Signals a build error.  The dep member points to the dependency node which
	failed to properly build.
	"""
	def __init__ (self, dep):
		self.failed_dep = dep

	def report (self, max_errors):
		for err in self.failed_dep.get_errors ():
			if max_errors == 0:
				msg.info (_("More errors."))
				return
			msg.display (**err)
			max_errors -= 1

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
		self.md5_for_source = {}
		# making is the lock guarding against making a node while making it
		self.making = False
		# date: timestamp when this Node was last successfully built.
		# is initialized to the mtime of the most recent product,
		# or to None if a product is missing.
		# when a build succeeds, it is set to time.time(), including fractional
		# seconds. in case building fails, it is set to None.
		self.date = 0  # 1970-01-01 (will be updated in add_product)

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
			self.md5_for_source[name] = None

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
			# meaning one of the products does not exist
			return True
		for source_name in self.sources:
			source = self.set[source_name]
			# NB: we ignore the case source.date == None (missing dependency) here.
			# NB2: to be extra correct, equal (disk-precision) timestamps trigger a recompile.
			if source.date == None:
				msg.debug(_("Not rebuilding %s from %s: unknown source timestamp") % (self.products[0], source_name), pkg="depend")
			elif source.date < self.date:
				msg.debug(_("Not rebuilding %s from %s: up to date") % (self.products[0], source_name), pkg="depend")
			elif not self.md5_for_source.has_key (source_name):
				msg.debug(_("Rebuilding %s from %s: outdated, source not tracked") % (self.products[0], source_name), pkg="depend")
				return True
			elif self.md5_for_source [source_name] == None:
				msg.debug(_("Rebuilding %s from %s: outdated, previous source unknown") % (self.products[0], source_name), pkg="depend")
				return True
			elif self.md5_for_source [source_name] != rubber.util.md5_file (source_name):
				msg.debug(_("Rebuilding %s from %s: outdated, source really modified") % (self.products[0], source_name), pkg="depend")
				return True
			else:
				msg.debug(_("Not rebuilding %s from %s: outdated, but source unmodified") % (self.products[0], source_name), pkg="depend")
		return False

	def make (self, force):
		"""
		Make our products, possibly making dependencies first, pruning cycles.
		Returns the total number of times run() was called in this subgraph, or
		raises BuildError.  If the argument force is true, run() is invoked
		at least once for each dep.
		"""
		# catch if cyclic dependencies have not been detected properly
		assert not self.making
		self.making = True
		deps_built = 0
		patience = 5
		primary_product = self.products[0]
		msg.debug(_("make %s -> %s") % (primary_product, str (self.sources)), pkg="depend")
		while patience > 0:
			# make our sources
			for source_name in self.sources:
				source = self.set[source_name]
				if source.making:
					# cyclic dependency -- drop for now, we will re-visit
					# this would happen while trying to remake the .aux in order to make the .bbl, for example
					msg.debug(_("while making %s: cyclic dependency on %s (pruned)") % (primary_product, source_name), pkg="depend")
					continue
				deps_built += source.make (force)

			must_make = force or self.should_make ()
			if not must_make:
				self.making = False
				return deps_built

			# record MD5 hash of source files as we now actually start the build
			for source_name in self.md5_for_source.keys ():
				self.md5_for_source[source_name] = rubber.util.md5_file (source_name)

			# actually make
			if not self.run ():
				raise BuildError (self)

			self.date = time.time ()
			force = False
			deps_built += 1
			patience -= 1

		msg.error(_("while making %s: file contents does not seem to settle") % self.products[0], pkg="depend")
		raise BuildError (self)

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
		Remove the files produced by this rule.  Note that cleaning is not
		done recursively; rather, all dependency nodes are cleaned in no
		particular order (see cmdline.py / cmd_pipe.py)

                Each override should start with
                super (class, self).clean ()
		"""
		for file in self.products:
			rubber.util.verbose_remove (file)
		self.date = None

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

	def make (self, force):
		# custom version to cut down on debug messages
		if not self.run ():
			raise BuildError (self)
		return 0

	def run (self):
		if self.date is not None:
			return True
		else:
			msg.error (_("%r does not exist, and cannot be made") % self.products[0], pkg="depend")
			return False

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
		msg.progress(_("running: %s") % ' '.join(self.command))
		process = Popen(self.command, stdin=devnull(), stdout=self.stdout)
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
		self.stdout = open(self.products[0], 'w')
		ret = super (Pipe, self).run ()
		self.stdout.close()
		return ret
