import hashlib
import logging
log = logging.getLogger (__name__)
import io
import os.path

_cache = {}

def snapshot (path):
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
    # We expect some files to be sources in many contexts, like the
    # main .tex document. In order to spare some checksum
    # computations, we cache the result.

    # Distinct paths refering to the same external file should be
    # rare, so we do not attempt to detect them.
    try:
        c, t = _cache [path]
    except KeyError:
        c, t = None, None

    if os.path.exists (path):
        mtime = os.path.getmtime (path)
        if c is None:
            log.debug ('%s contents are now watched', path)
            c = _checksum_algorithm (path)
            t = mtime
        elif c == NO_SUCH_FILE:
            log.debug ('%s has been created', path)
            c = _checksum_algorithm (path)
            t = mtime
        elif t == mtime:
            log.debug ('%s has the same mtime', path)
        else:
            assert t < mtime, 'mtime decreased: ' + path
            t = mtime
            checksum = _checksum_algorithm (path)
            if checksum == c:
                log.debug ('%s rewritten with same checksum', path)
            else:
                log.debug ('%s rewritten with new contents.', path)
                c = checksum
    elif c is None:
        log.debug ('%s will be watched once created', path)
        c = NO_SUCH_FILE
    else:
        assert c == NO_SUCH_FILE, path + ' vanished'
        log.debug ('%s does not exist yet',  path)

    _cache [path] = (c, t)
    return c

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
# s0 = snapshot (t)
# assert snapshot (t) == s0
# assert s0 == NO_SUCH_FILE

# print ('writing foo')
# with open (t, 'w') as f:
#     f.write ('foo')

# time.sleep (0.1)
# s1 = snapshot (t)
# assert s1 != NO_SUCH_FILE

# time.sleep (0.1)
# assert snapshot (t) == s1

# print ('writing bar')
# with open (t, 'w') as f:
#     f.write ('bar')

# time.sleep (0.1)
# s2 = snapshot (t)
# assert s2 != NO_SUCH_FILE
# assert s2 != s1

# time.sleep (0.1)
# assert snapshot (t) == s2

# print ('writing bar')
# with open (t, 'w') as f:
#     f.write ('bar')

# time.sleep (0.1)
# assert snapshot (t) == s2

# os.remove (t)
# print ('OK')
