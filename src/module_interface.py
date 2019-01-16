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
from rubber.util import _
import logging
msg = logging.getLogger (__name__)
import rubber.util

class Module:
    # This class may not be instantiated directly, only subclassed.
    __metaclass__ = abc.ABCMeta

    """
    This is the base class for modules. Each module should define a class
    named 'Module' that derives from this one. The default implementation
    provides all required methods with no effects.

    The constructor is mandatory. Its profile must be
    def __init__ (self, document, opt):

    'document' is the compiling environment (an instance of
    converters.latex.LaTeXDep)

    'opt' describes the option given to the macro that caused
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
        Remove additional files for this LaTeX module.
        Nothing recursive happens here.
        Files registered as products are removed by rubber.clean ().
        """

    def command (self, cmd, args, _dep = None):
        """
        This is called when a directive for the module is found in the source.
        We treat syntax errors in the directive as fatal, aborting the run.

        The _dep parameter is an implementation detail and must not
        be used outside the latex_modules subdirectory.
        When absent, self.dep is tried.
        """
        try:
            if _dep is None:
                _dep = self.dep  # may raise AttributeError
            handler = getattr (_dep, "do_" + cmd) # may raise AttributeError
        except AttributeError:
            # there is no do_ method for this directive, which means there
            # is no such directive.
            raise rubber.SyntaxError (_("no such directive '%s' (in module %s)") % (cmd, self.__module__))
        handler (args)

    def get_errors (self):
        """
        This is called if something has failed during an operation performed
        by this module. The method returns a generator with items of the same
        form as in LaTeXDep.get_errors.
        """
        # TODO: what does this mean (copied from rubber.converters.latex)?
        if None:
            yield None
