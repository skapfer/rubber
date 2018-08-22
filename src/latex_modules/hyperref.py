import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):

        brf = document.basename (with_suffix = '.brf')
        document.add_product (brf)

        out = document.basename (with_suffix = '.out')
        document.add_product (out)
        document.watch_file (out)
