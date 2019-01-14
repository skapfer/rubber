import hashlib
import logging
log = logging.getLogger (__name__)
import io
import os.path

def factory (path):
    """
    Must be used instead of the constructor.
    """
    try:
        result = _file_by_path [path]
        log.debug ('reusing _File instance for ' + path)
    except KeyError:
        result = _File (path)
        _file_by_path [path] = result
    return result

_file_by_path = {}

class _File:

    def __init__ (self, path):
        """
        This constructor is private, use Contents.factory (path) instead.
        """
        log.debug ('new _File: ' + path)
        self._path     = path
        self._producer = None
        self._checksum = None

    def path (self):
        return self._path

    def producer (self):
        return self._producer

    def set_producer (self, producer):
        assert producer is not None
        self._producer = producer

    def snapshot (self):
        """
        A snapshot of the contents of an external file.

        The special value NO_SUCH_FILE is returned when path does not
        refer to an existing external file. However, an exception is
        raised if an existing file vanishes between two calls.

        The implementation trusts the operating system about modification
        times, and assumes that an unchanged time stamp implies unchanged
        contents. Malicious or unadvised users may change timestamps.

        Moreover, an overwrite will not be detected if it is more recent
        than the smallest interval representable by operating timestamps.

        The implementation relies on the MD5 hash to detect modified
        contents. For such a non-cryptographic use,  the probability of
        collision (2^-64) can be neglected for all practical needs.
        """

        # We expect some files to be sources in many context, like the
        # main .tex document. In order to spare some checksum
        # computations, we cache the result.

        # Distinct paths refering to the same external file should be
        # rare, so we do not attempt to detect them.
        if os.path.exists (self._path):
            mtime = os.path.getmtime (self._path)
            if self._checksum is None:
                log.debug ('%s contents are now watched', self._path)
                self._checksum = _checksum_algorithm (self._path)
                self._mtime    = mtime
            elif self._checksum == NO_SUCH_FILE:
                log.debug ('%s has been created', self._path)
                self._checksum = _checksum_algorithm (self._path)
                self._mtime    = mtime
            elif self._mtime == mtime:
                log.debug ('%s has the same mtime', self._path)
            else:
                assert self._mtime < mtime, 'mtime decreased: ' + self._path
                self._mtime = mtime
                checksum = _checksum_algorithm (self._path)
                if checksum == self._checksum:
                    log.debug ('%s rewritten with same checksum', self._path)
                else:
                    log.debug ('%s rewritten with new contents.', self._path)
                    self._checksum = checksum
        elif self._checksum is None:
            log.debug ('%s will be watched once created', self._path)
            self._checksum = NO_SUCH_FILE
        else:
            assert self._checksum == NO_SUCH_FILE, self._path + ' vanished'
            log.debug ('%s does not exist yet',  self._path)
        return self._checksum

# Md5 values are represented as bytes. None is used above.
NO_SUCH_FILE = bytes ()

def _checksum_algorithm (path):
    with open (path, 'br') as stream:
        result = hashlib.md5 ()
        while True:
            data = stream.read (io.DEFAULT_BUFFER_SIZE)
            if not data:
                return result.digest ()
            result.update (data)

# These two functions encapsulate the hexadecimal representation of
# checksums other than NO_SUCH_FILE.  In order to ease formatting, all
# results are guaranteed to have a common length.
cs_str_len = 32
def cs2str (checksum):
    if checksum == NO_SUCH_FILE:
        result = 'No such file                    '
    else:
        result = ''.join ('{:02X}'.format (byte) for byte in checksum)
    assert len (result) == cs_str_len
    return result
def str2cs (string):
    assert len (string) == cs_str_len
    if string == 'No such file                    ':
        return NO_SUCH_FILE
    else:
        return bytes (int (string [i:i+2], base=16)
                      for i in range (0, len (string), 2))

# Manual tests

# import time
# logging.basicConfig (level = logging.DEBUG)
# t = 'tmpfile'
# if os.path.exists (t):
#     os.remove (t)

# time.sleep (0.1)
# c = factory (t)
# assert factory (t) is c
# assert c.snapshot () == NO_SUCH_FILE

# print ('writing foo')
# with open (t, 'w') as f:
#     f.write ('foo')

# time.sleep (0.1)
# s1 = c.snapshot ()
# assert s1 != NO_SUCH_FILE

# time.sleep (0.1)
# assert c.snapshot () == s1

# print ('writing bar')
# with open (t, 'w') as f:
#     f.write ('bar')

# time.sleep (0.1)
# s2 = c.snapshot ()
# assert s2 != NO_SUCH_FILE
# assert s2 != s1

# time.sleep (0.1)
# assert c.snapshot () == s2

# print ('writing bar')
# with open (t, 'w') as f:
#     f.write ('bar')

# time.sleep (0.1)
# assert c.snapshot () == s2

# os.remove (t)
