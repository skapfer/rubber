import binascii
import logging
log = logging.getLogger (__name__)
import io
import os.path

def contents (path):
    """
    A snapshot of the contents of an external file.

    The result is always an int. You may rely on the fact that no
    other kind of value will ever be returned.

    The special int value NO_SUCH_FILE is returned when path does not
    refer to an existing external file. However, an exception is
    raised if an existing file vanishes between two calls.

    The implementation trusts the operating system about modification
    times, and assumes that an unchanged time stamp implies unchanged
    contents. Malicious or unadvised users may change timestamps.

    Moreover, an overwrite will not be detected if it is more recent
    than the smallest interval representable by operating timestamps.

    The implementation trusts a non-cryptographic hash to detect
    modified contents. With the current algorithm, there will be in
    average 1 error in 65536 files reported as unchanged.
    """

    # We expect some files to be sources in many context, like the
    # main .tex document. In order to spare some checksum
    # computations, we cache the result.

    # Distinct paths refering to the same external file should be
    # rare, so we do not attempt to detect them.

    if os.path.exists (path):
        mtime = os.path.getmtime (path)
        if path in cache:
            old = cache [path]
            if old is None:
                log.debug ('%s has been created', path)
                result = checksum_algorithm (path)
            elif old [0] == mtime:
                log.debug ('%s has the same mtime', path)
                return old [1]
            else:
                assert old [0] < mtime, path + ' mtime has decreased'
                result = checksum_algorithm (path)
                if result == old [1]:
                    log.debug ('%s rewritten with same checksum', path)
                else:
                    log.debug ('%s rewritten with new contents.', path)
        else:
            log.debug ('%s contents are now watched', path)
            result = checksum_algorithm (path)
        cache [path] = (mtime, result)
        return result
    else:
        if path in cache:
            log.debug ('%s does not exist yet',  path)
            assert cache [path] is None, path + ' has vanished'
        else:
            log.debug ('%s will be watched once created', path)
            cache [path] = None
        return NO_SUCH_FILE

cache = {}

NO_SUCH_FILE = 2**32

def checksum_algorithm (path):
    result = 0
    with open (path, 'br') as stream:
        while True:
            data = stream.read (io.DEFAULT_BUFFER_SIZE)
            if not data:
                break
            result = binascii.crc32 (data, result)
    return result

# Manual tests

# import time
# logging.basicConfig (level = logging.DEBUG)
# t = 'tmpfile'
# if os.path.exists (t):
#     os.remove (t)

# time.sleep (0.1)
# assert contents (t) == NO_SUCH_FILE

# time.sleep (0.1)
# assert contents (t) == NO_SUCH_FILE
# # Successive calls desserve to be tested because of the cache.

# print ('writing foo')
# with open (t, 'w') as f:
#     f.write ('foo')

# time.sleep (0.1)
# s1 = contents (t)
# assert s1 != NO_SUCH_FILE

# time.sleep (0.1)
# assert contents (t) == s1

# print ('writing bar')
# with open (t, 'w') as f:
#     f.write ('bar')

# time.sleep (0.1)
# s2 = contents (t)
# assert s2 != NO_SUCH_FILE
# assert s2 != s1

# time.sleep (0.1)
# assert contents (t) == s2

# print ('writing bar')
# with open (t, 'w') as f:
#     f.write ('bar')

# time.sleep (0.1)
# assert contents (t) == s2

# os.remove (t)
