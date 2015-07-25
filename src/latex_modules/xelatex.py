from rubber import _, msg
import rubber.module_interface

class Module (rubber.module_interface.Module):

    def __init__ (self, document, context):
        document.vars['program'] = 'xelatex'
        document.vars['engine'] = 'XeLaTeX'

        if document.env.final != document and document.products[0][-4:] != '.pdf':
            msg.error(_("there is already a post-processor registered"))
            return

        document.set_primary_product_suffix (".pdf")
