#!/bin/sh
# really basic test driver
# copy the rubber source, and the test case data to a temporary
# directory, and run rubber on the file.

SOURCE_DIR="$(cd ..; pwd)"
TMPDIR=tmp

set -e                          # Stop at first failure.

VERBOSE=
if test 1 -le $#; then
    case $1 in
        -v)
            VERBOSE=$1
            shift
            ;;
    esac
fi

echo "When a test fails, please remove the $TMPDIR directory manually."

for main; do
    [ -d $main ] || {
        echo $main must be a directory >&2
        exit 1
    }

    doc=doc
    [ -e $main/document ] && doc=$(cat $main/document)

    [ -e $main/arguments ] && arguments=$(cat $main/arguments)

    for format in "" "--pdf" "--ps --pdf"; do
        echo Test:$main, format:$format

        mkdir $TMPDIR
        cp $main/* $TMPDIR
        cd $TMPDIR

        cat > usrbinrubber.py <<EOF
import sys, rubber.cmdline
sys.exit (rubber.cmdline.Main () (sys.argv [1:]))
EOF
        cp -a "$SOURCE_DIR/src" rubber
        cat >> rubber/version.py <<EOF
version = "unreleased"
moddir = "$SOURCE_DIR/src/rubber/git/data"
EOF

        python usrbinrubber.py $VERBOSE $format $arguments         $doc
        python usrbinrubber.py $VERBOSE $format $arguments         $doc
        python usrbinrubber.py $VERBOSE $format $arguments --clean $doc

        rm -r rubber
        rm usrbinrubber.py
        (cd ../$main; find -mindepth 1 -print0) | xargs -0 rm -r
        cd ..
        rmdir $TMPDIR           # Fail if not clean.
    done
done

echo OK
