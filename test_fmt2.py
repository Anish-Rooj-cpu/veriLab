import sys
from PyQt5.QtWidgets import QApplication, QTextEdit
from highlighter import VerilogHighlighter

app = QApplication(sys.argv)
edit = QTextEdit()
edit.setPlainText('always 1''b0 // comment')
highlighter = VerilogHighlighter(edit.document())
edit.show()
highlighter.rehighlight()

# Dump formats
block = edit.document().firstBlock()
while block.isValid():
    print('Block:', block.text())
    for f in block.layout().formats():
        print(f'  {f.start} - {f.start + f.length}: {f.format.foreground().color().name()}')
    block = block.next()
