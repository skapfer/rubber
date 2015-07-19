#!/bin/sh
# really basic test driver
# copy the rubber source, and the test case data to a temporary
# directory, and run rubber on the file.

SOURCE_DIR="$(cd ..; pwd)"
TMPDIR=tmp

set -e                          # Stop at first failure.

KEEP=false
VERBOSE=
while [ 1 -le $# ]; do
    case $1 in
        -k)
            KEEP=true
            shift
            ;;
        -v|-vv|-vvv)
            VERBOSE="$VERBOSE $1"
            shift
            ;;
        *)
            break
    esac
done

echo "When a test fails, please remove the $TMPDIR directory manually."

list0() {
    (cd "$1"; find -mindepth 1 -print0)
}

for main; do
    [ "$main" = 'run.sh' ] && continue

    [ -d $main ] || {
        echo $main must be a directory >&2
        exit 1
    }

    [ -e $main/disable ] && {
        echo Skipping test $main >&2
        continue
    }

    doc=doc
    [ -e $main/document ] && doc=$(cat $main/document)

    [ -e $main/arguments ] && arguments=$(cat $main/arguments)

        echo Test:$main

        mkdir $TMPDIR
        cp $main/* $TMPDIR
        cp shared/* $TMPDIR
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

        python usrbinrubber.py $VERBOSE $arguments         $doc

        if $KEEP; then
            echo "keeping tmp." >&2
            exit 1
        fi

        python usrbinrubber.py $VERBOSE $arguments         $doc
        python usrbinrubber.py $VERBOSE $arguments --clean $doc

        rm -r rubber
        rm usrbinrubber.py
        (list0 ../$main; list0 ../shared) | xargs -0 rm -r
        cd ..
        rmdir $TMPDIR           # Fail if not clean.
done

echo OK
