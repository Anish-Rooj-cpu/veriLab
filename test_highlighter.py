import sys
from PyQt5.QtWidgets import QApplication, QTextEdit
from PyQt5.QtGui import QTextDocument
from highlighter import VerilogHighlighter

app = QApplication(sys.argv)
doc = QTextDocument("module test;\nendmodule")
highlighter = VerilogHighlighter(doc)
print("Highlighter initialized")
