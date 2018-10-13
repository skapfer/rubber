import rubber.depend
import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):
        job = document.basename ()
        glo = job + '.glo'

        document.add_product (job + '.ist')
        document.add_source (glo)

        dep = rubber.depend.Shell (('makeglossaries', job))
        # FIXME: does probably fail with --inplace and friends.
        dep.add_product (glo)
        dep.add_product (job + '.gls')
        dep.add_product (job + '.glg')
        dep.add_source (job + '.aux')
