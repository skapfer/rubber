#!/bin/sh

SOURCE_DIR="$(cd ..; pwd)"
TMPDIR=tmp

set -e                          # Stop at first failure.

VERBOSE=
if test 1 -le $#; then
    case $1 in
        -q | -vvv | -vv | -v)
            VERBOSE=$1
            shift
            ;;
    esac
fi
for main; do
    if test ${main%.tex} = $main; then
        echo "Usage: sh $0 [-q|-v|-vv|-vvv] [file.tex ..]"
        exit 1
    fi
done

echo "When a test fails, please remove the $TMPDIR directory manually."

for main; do
    for format in "" "--pdf" "--ps --pdf"; do
        echo Test:$main, format:$format

        mkdir $TMPDIR
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

        python usrbinrubber.py $VERBOSE $format         ../$main
        python usrbinrubber.py $VERBOSE $format         ../$main
        python usrbinrubber.py $VERBOSE $format --clean ../$main

        rm -r rubber
        rm usrbinrubber.py
        cd ..
        rmdir $TMPDIR           # Fail if not clean.
    done
done

echo OK
