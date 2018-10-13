from rubber.util import _
import logging
msg = logging.getLogger (__name__)
import os.path
import rubber.depend
import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):
        job = document.basename ()
        glo = job + '.glo'

        document.add_product (job + '.ist')
        document.add_source (glo)

        dep = Dep (document.set, ('makeglossaries', job))
        # FIXME: does probably fail with --inplace and friends.
        dep.add_product (glo)
        dep.add_product (job + '.gls')
        dep.add_product (job + '.glg')
        dep.add_source (job + '.aux')

class Dep (rubber.depend.Shell):

    def run (self):
        aux = self.command [1] + '.aux'
        if not os.path.exists (aux):
            msg.info (_("%s does not exist yet, deferring makeglossaries"), aux)
            return True
        return super ().run ()
