# This file is part of Rubber and thus covered by the GPL
import rubber.dvip_tool
class Module (rubber.dvip_tool.Module):
    def __init__ (self, document, context):
        super (Module, self).__init__ (document, context, self.__module__)
