#!/bin/sh
# really basic test driver
# copy the rubber source, and the test case data to a temporary
# directory, and run rubber on the file.

SOURCE_DIR="$(cd ..; pwd)"
tmpdir=tmp
python=python3

set -e                          # Stop at first failure.

KEEP=false
VERBOSE=
while [ 1 -le $# ]; do
    case $1 in
        --rmtmp)
            rm -rf $tmpdir
            ;;
        -k)
            KEEP=true
            ;;
        -v|-vv|-vvv)
            VERBOSE="$VERBOSE $1"
            ;;
        --debchroot)
            # Dependencies inside Debian.
            apt install -y \
                debhelper dh-python python3 texlive-latex-base asymptote \
                biber imagemagick python-prompt-toolkit python-pygments \
                python3-prompt-toolkit python3-pygments r-cran-knitr \
                texlive-bibtex-extra texlive-binaries texlive-extra-utils \
                texlive-latex-extra texlive-latex-recommended \
                texlive-metapost texlive-omega texlive-pictures transfig
            # combine is not packaged for Debian.
            touch combine/disable
            ;;
        *)
            break
    esac
    shift
done

echo "When a test fails, please remove the $tmpdir directory manually."

# Copy source directory, because we must patch version.py and python
# will attempt to write precompiled *.pyc sources.  For efficiency,
# we share these temporary files among tests.
mkdir $tmpdir
cp -a "$SOURCE_DIR/src" $tmpdir/rubber
sed "s%@version@%unreleased%;s%@moddir@%$SOURCE_DIR/data%" \
    $tmpdir/rubber/version.py.in > $tmpdir/rubber/version.py
# Also rename rubber to rubber.py to avoid a clash with rubber/.
for exe in rubber rubber-info rubber-pipe; do
    cp "$SOURCE_DIR/$exe" $tmpdir/$exe.py
done

for main; do
    case "$main" in
        run.sh | shared | $tmpdir)
            continue;;
    esac

    [ -d $main ] || {
        echo "$main must be a directory"
        exit 1
    }

    [ -e $main/disable ] && {
        echo "Skipping test $main"
        continue
    }

    echo "Test: $main"

    mkdir $tmpdir/$main
    cp $main/* shared/* $tmpdir/$main
    cd $tmpdir/$main

    if test -r document; then
        read doc < document
    else
        doc=doc
    fi
    if test -r arguments; then
        read arguments < arguments
    fi

    if [ -e fragment ]; then
        # test brings their own code
        . ./fragment
    else
        # default test code:  try to build two times, clean up.
        echo "Running $python ../rubber.py $VERBOSE $arguments $doc ..."
        $python ../rubber.py $VERBOSE $arguments "$doc"
    fi

    if $KEEP; then
        echo "Keeping $tmpdir/$main."
        exit 1
    fi

    ([ -r expected ] && cat expected ) | while read f; do
        [ -e "$f" ] || {
            echo "Expected file $f was not produced."
            exit 1
        }
    done

    if ! [ -e fragment ]; then
        # default test code:  try to build two times, clean up.
        $python ../rubber.py $VERBOSE $arguments         "$doc"
        $python ../rubber.py $VERBOSE $arguments --clean "$doc"
    fi

    unset doc arguments

    cd ../..

    for before in $main/* shared/*; do
        after=$tmpdir/$main/${before##*/}
        diff $before $after || {
            echo "File $after missing or changed"
            exit 1
        }
        rm $after
    done

    rmdir $tmpdir/$main || {
        echo "Directory $tmpdir/$main is not left clean:"
        ls $tmpdir/$main
        exit 1
    }
done

rm -fr $tmpdir

echo OK
