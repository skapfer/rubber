# module_interface.py, part of Rubber building system for LaTeX documents..

# Copyright (C) 2015-2015 Nicolas Boulenguez <nicolas.boulenguez@free.fr>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This module defines the common interface for all rubber modules.

Most of them are implemented as Python modules under
rubber.latex_modules.  Each one contains a subclass of
rubber.module_interface.Module that will be instantiated once when the
plugin is loaded by rubber.converters.latex.

rubber.converters.latex also declares a subclass that is instantiated
each time a .rub file is read.
"""

import abc
from rubber import msg, _
import rubber.util

class Module:
    # This class may not be instantiated directly, only subclassed.
    __metaclass__ = abc.ABCMeta

    """
    This is the base class for modules. Each module should define a class
    named 'Module' that derives from this one. The default implementation
    provides all required methods with no effects.

    The constructor is mandatory. Its profile must be
    def __init__ (self, document, context):

    'document' is the compiling environment (an instance of
    converters.latex.LaTeXDep)

    'context' is a dictionary that describes the command that caused
    the module to load.
    """

    def pre_compile (self):
        """
        This method is called before the first LaTeX compilation. It is
        supposed to build any file that LaTeX would require to compile the
        document correctly. The method must return true on success.
        """
        return True

    def post_compile (self):
        """
        This method is called after each LaTeX compilation. It is supposed to
        process the compilation results and possibly request a new
        compilation. The method must return true on success.
        """
        return True

    def clean (self):
        """
        This method is called when cleaning the compiled files. It is supposed
        to remove all the files that this modules generates.
        """

    def command (self, cmd, args):
        """
        This is called when a directive for the module is found in the source.
        We treat syntax errors in the directive as fatal, aborting the run.
        """
        try:
            handler = getattr (self, "do_" + cmd)
        except AttributeError:
            # there is no do_ method for this directive, which means there
            # is no such directive.
            msg.error (_("no such directive '%s'") % cmd, pkg=self.__module__)
            rubber.util.abort_rubber_syntax_error ()
        try:
            return handler (*args)
        except TypeError:
            # Python failed to coerce the arguments given into whatever
            # the handler would like to see.  report a generic failure.
            msg.error (_("invalid syntax for directive '%s'") % cmd, pkg=self.__module__)
            rubber.util.abort_rubber_syntax_error ()

    def get_errors (self):
        """
        This is called if something has failed during an operation performed
        by this module. The method returns a generator with items of the same
        form as in LaTeXDep.get_errors.
        """
        # TODO: what does this mean (copied from rubber.converters.latex)?
        if None:
            yield None
