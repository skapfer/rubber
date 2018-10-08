import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):
        document.program = 'xelatex'
        document.engine = 'XeLaTeX'
        document.register_post_processor (old_suffix='.pdf', new_suffix='.pdf')
