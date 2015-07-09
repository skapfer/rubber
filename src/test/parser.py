#!/usr/bin/env python
# vim: noet:ts=4
from rubber.tex import *
import unittest

class TestTexParser(unittest.TestCase):

	def assert_cseq(self, val):
		t = self.p.get_token()
		self.assertEqual(t.cat, CSEQ)
		self.assertEqual(t.val, val)

	def assert_latex_optional_text(self, ot):
		self.assertEqual(self.p.get_latex_optional_text(), ot)

	def assert_argument_text(self, at):
		self.assertEqual(self.p.get_argument_text(), at)

	def assert_eof(self):
		self.assertEqual(self.p.get_token().cat, EOF)

class TestMacroWithArgument(TestTexParser):
	def run_it(self, c):
		self.p = parse_string(c)
		self.assert_cseq("usepackage")
		self.assert_argument_text("aloha4")
		self.assert_eof()

	def test_latexmacro1(self):
		self.run_it("\\usepackage{aloha4}")

	def test_latexmacro2(self):
		self.run_it("\\usepackage {aloha4}")

	def test_latexmacro3(self):
		self.run_it("\\usepackage%comment\n{aloha4}")

	def test_latexmacro4(self):
		self.run_it("\\usepackage\n%comment\n{aloha4}")

class TestMacroWithLatexOptional(TestTexParser):
	def run_it(self, c):
		self.p = parse_string(c)
		self.assert_cseq("usepackage")
		self.assert_latex_optional_text("aloha1,aloha2=aloha3")
		self.assert_argument_text("aloha4")
		self.assert_eof()

	def test_latexmacro1(self):
		self.run_it("\\usepackage[aloha1,aloha2=aloha3]{aloha4}")

	def test_latexmacro2(self):
		self.run_it("\\usepackage [aloha1,aloha2=aloha3] {aloha4}")

	def test_latexmacro3(self):
		self.run_it("\\usepackage%comment\n[aloha1,aloha2=aloha3]%comment\n{aloha4}")

	def test_latexmacro4(self):
		self.run_it("\\usepackage\n[aloha1,aloha2=aloha3]{aloha4}")

	def test_latexmacro5(self):
		self.run_it("\\usepackage[aloha1,aloha2=aloha3]\n{aloha4}")

if __name__ == '__main__':
	unittest.main()
