# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2002--2006

import rubber.index
import rubber.module_interface

class Module (rubber.index.Index, rubber.module_interface.Module):
    def __init__ (self, document, context):
        super (Module, self).__init__ (document, 'idx', 'ind', 'ilg')
