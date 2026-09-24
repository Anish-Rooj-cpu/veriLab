from PyQt5.QtWidgets import QPlainTextEdit, QWidget, QTextEdit, QCompleter
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QTextFormat, QFont, QTextCursor, QTextCharFormat

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.lineNumberArea = LineNumberArea(self)
        self._completer = None
        self._errors = set() # Set of line numbers (0-indexed) with errors

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

        font = QFont("Consolas", 11)
        self.setFont(font)
        
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                selection-background-color: #264F78;
            }
        """)

    def lineNumberAreaWidth(self):
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num /= 10
            digits += 1
        
        # calculate width based on digits
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def setErrors(self, error_lines):
        self._errors = set(error_lines)
        self.highlightCurrentLine()

    def highlightCurrentLine(self):
        extraSelections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor("#2A2D2E")
            
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        # Add error squiggles
        for line_idx in self._errors:
            block = self.document().findBlockByNumber(line_idx)
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.format.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
                selection.format.setUnderlineColor(QColor("red"))
                
                cursor = QTextCursor(block)
                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                selection.cursor = cursor
                extraSelections.append(selection)

        self.setExtraSelections(extraSelections)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#1E1E1E"))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#858585"))
                painter.drawText(0, int(top), self.lineNumberArea.width() - 2, self.fontMetrics().height(),
                                 Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    def setCompleter(self, completer):
        if self._completer:
            self._completer.disconnect(self)
        self._completer = completer
        if not self._completer:
            return
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.activated.connect(self.insertCompletion)

    def insertCompletion(self, completion):
        if self._completer.widget() is not self:
            return
        tc = self.textCursor()
        extra = len(completion) - len(self._completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        return tc.selectedText()

    def focusInEvent(self, e):
        if self._completer:
            self._completer.setWidget(self)
        super().focusInEvent(e)

    def keyPressEvent(self, e):
        if self._completer and self._completer.popup().isVisible():
            if e.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                e.ignore()
                return

        isShortcut = ((e.modifiers() & Qt.ControlModifier) and e.key() == Qt.Key_Space)
        if not self._completer or not isShortcut:
            super().keyPressEvent(e)

        ctrlOrShift = e.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)
        if not self._completer or (ctrlOrShift and e.text() == ''):
            return

        hasModifier = (e.modifiers() != Qt.NoModifier) and not ctrlOrShift
        completionPrefix = self.textUnderCursor()

        if not isShortcut and (hasModifier or e.text() == '' or len(completionPrefix) < 2):
            self._completer.popup().hide()
            return

        if completionPrefix != self._completer.completionPrefix():
            self._completer.setCompletionPrefix(completionPrefix)
            self._completer.popup().setCurrentIndex(self._completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self._completer.popup().sizeHintForColumn(0) + self._completer.popup().verticalScrollBar().sizeHint().width())
        self._completer.complete(cr)
