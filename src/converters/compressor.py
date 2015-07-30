# This file is part of Rubber and thus covered by the GPL
# (c) Nicolas Boulenguez 2015
"""
Compressing the output of Rubber.
"""

from rubber import _, msg
import rubber.depend

class Node (rubber.depend.Node):

    def __init__ (self, node_dictionary, constructor, extension, source):
        super (Node, self).__init__ (node_dictionary)
        self.constructor = constructor
        self.target = source + extension
        self.source = source
        self.add_product (self.target)
        self.add_source (source)

    def run (self):
        msg.progress (_ ("compressing %s into %s") % (self.source, self.target))
        try:
            with open (self.source, 'rb') as f_in:
                with self.constructor (self.target, 'wb') as f_out:
                    f_out.writelines (f_in)
        except:
            msg.error (_ ("compression failed"))
            return False
        return True
