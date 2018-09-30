# This file is part of Rubber and thus covered by the GPL

import rubber.dvip_tool
import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):
        self.dep = rubber.dvip_tool.Dvip_Tool_Dep_Node (document, 'dvips')
