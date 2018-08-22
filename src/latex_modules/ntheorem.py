import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):

        thm = document.basename (with_suffix = '.thm')
        document.add_product (thm)
        document.watch_file (thm)
