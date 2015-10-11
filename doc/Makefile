all: rubber.info

rubber.info: rubber.texi
	makeinfo rubber.texi

rubber.dvi: rubber.texi
	texi2dvi rubber.texi

rubber.html html:
	makeinfo --html --no-split -o rubber.html rubber.texi

distclean clean:
	rm -f rubber.html
	rm -f rubber.aux rubber.cp rubber.dvi rubber.fn rubber.fns \
		rubber.info rubber.ky rubber.log rubber.pg \
		rubber.toc rubber.tp rubber.vr rubber.vrs
