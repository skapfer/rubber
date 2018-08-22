import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):

        nav = document.basename (with_suffix = '.nav')
        document.add_product (nav)
        document.watch_file (nav)

        snm = document.basename (with_suffix = '.snm')
        document.add_product (snm)
        document.watch_file (snm)

        toc = document.basename (with_suffix = '.toc')
        document.add_product (toc)
        document.watch_file (toc)

        document.modules.register ('hyperref')
