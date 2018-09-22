from rubber.util import _
import logging
msg = logging.getLogger (__name__)
import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, opt):
        document.program = 'xelatex'
        document.engine = 'XeLaTeX'

        if document.env.final != document and document.products[0][-4:] != '.pdf':
            msg.error(_("there is already a post-processor registered"))
            return

        document.set_primary_product_suffix (".pdf")
