import rubber.module_interface
class Module (rubber.module_interface.Module):
    def __init__ (self, document, opt):

        glo = document.basename (with_suffix = '.glo')
        document.watch_file (glo)
        document.onchange_md5 [glo] = md5_file (glo)
        # FIXME: does probably fail with --inplace and friends.
        document.onchange_cmd [glo] = 'makeglossaries ' + document.basename ()
