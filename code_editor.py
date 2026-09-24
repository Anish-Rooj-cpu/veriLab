from PyQt5.QtWidgets import QPlainTextEdit, QWidget, QTextEdit, QCompleter
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QTextFormat, QFont, QTextCursor, QTextCharFormat, QTextBlockUserData

class BlockData(QTextBlockUserData):
    def __init__(self):
        super().__init__()
        self.folded = False

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

    def mousePressEvent(self, event):
        self.codeEditor.lineNumberAreaMousePressEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.lineNumberArea = LineNumberArea(self)
        self._completer = None
        self._errors = set() # Set of line numbers (0-indexed) with errors
        self.extra_cursors = []

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

        font = QFont("Consolas", 13)
        self.setFont(font)
        
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #282C34;
                color: #ABB2BF;
                selection-background-color: #3E4451;
                border: none;
            }
        """)

    def lineNumberAreaWidth(self):
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num /= 10
            digits += 1
        
        # calculate width based on digits plus space for fold icon
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits + 15
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
        
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setPen(QColor("#3E4451"))
        
        block = self.firstVisibleBlock()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        space_width = self.fontMetrics().horizontalAdvance(' ')
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                text = block.text()
                indent = len(text) - len(text.lstrip(' '))
                if not text.strip():
                    prev_b = block.previous()
                    while prev_b.isValid() and not prev_b.text().strip():
                        prev_b = prev_b.previous()
                    if prev_b.isValid():
                        indent = len(prev_b.text()) - len(prev_b.text().lstrip(' '))
                        
                for i in range(1, indent // 4 + 1):
                    x = self.document().documentMargin() + (i * 4 * space_width) + self.contentOffset().x()
                    painter.drawLine(int(x), int(top), int(x), int(bottom))
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()

    def highlightCurrentLine(self):
        extraSelections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor("#2C313A")
            
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
                selection.format.setUnderlineColor(QColor("#E06C75"))
                
                cursor = QTextCursor(block)
                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                selection.cursor = cursor
                extraSelections.append(selection)

        # Draw extra cursors
        for cursor in getattr(self, 'extra_cursors', []):
            # Block highlight
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#2C313A"))
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = cursor
            selection.cursor.clearSelection()
            extraSelections.append(selection)
            
            # Cursor tick mark (1 char inverted)
            c_sel = QTextEdit.ExtraSelection()
            c_sel.cursor = QTextCursor(cursor)
            c_sel.cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
            c_sel.format.setBackground(QColor("#ABB2BF"))
            c_sel.format.setForeground(QColor("#282C34"))
            extraSelections.append(c_sel)

        self.setExtraSelections(extraSelections)

    def get_indent(self, block):
        text = block.text()
        if not text.strip(): return -1
        return len(text) - len(text.lstrip())

    def is_fold_start(self, block):
        indent = self.get_indent(block)
        if indent == -1: return False
        
        next_b = block.next()
        while next_b.isValid() and self.get_indent(next_b) == -1:
            next_b = next_b.next()
            
        if next_b.isValid():
            next_indent = self.get_indent(next_b)
            return next_indent > indent
        return False

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#282C34"))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        fold_x = self.lineNumberArea.width() - 12

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#4B5263"))
                painter.drawText(0, int(top), self.lineNumberArea.width() - 16, self.fontMetrics().height(),
                                 Qt.AlignRight, number)
                                 
                if self.is_fold_start(block):
                    data = block.userData()
                    if not isinstance(data, BlockData):
                        data = BlockData()
                        block.setUserData(data)
                        
                    # draw +/- box
                    painter.setPen(QColor("#ABB2BF"))
                    painter.drawRect(fold_x, int(top) + 4, 8, 8)
                    painter.drawLine(fold_x + 2, int(top) + 8, fold_x + 6, int(top) + 8)
                    if data.folded:
                        painter.drawLine(fold_x + 4, int(top) + 6, fold_x + 4, int(top) + 10)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    def lineNumberAreaMousePressEvent(self, event):
        fold_x = self.lineNumberArea.width() - 14
        if event.pos().x() >= fold_x:
            block = self.firstVisibleBlock()
            top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
            bottom = top + self.blockBoundingRect(block).height()
            
            while block.isValid() and top <= self.viewport().rect().bottom():
                if block.isVisible() and top <= event.pos().y() <= bottom:
                    if self.is_fold_start(block):
                        data = block.userData()
                        if not isinstance(data, BlockData):
                            data = BlockData()
                            block.setUserData(data)
                        
                        data.folded = not data.folded
                        self.toggle_fold(block, data.folded)
                        self.viewport().update()
                        self.lineNumberArea.update()
                        self.updateRequest.emit(self.viewport().rect(), 0) # Force recalculation of block layout
                    break
                block = block.next()
                top = bottom
                bottom = top + self.blockBoundingRect(block).height()
                
    def toggle_fold(self, start_block, folded):
        base_indent = self.get_indent(start_block)
        block = start_block.next()
        
        while block.isValid():
            indent = self.get_indent(block)
            if indent != -1 and indent <= base_indent:
                break # We reached the end of the folded section
            block.setVisible(not folded)
            block = block.next()
            
        self.document().markContentsDirty(start_block.position(), block.position() - start_block.position() if block.isValid() else self.document().characterCount())

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

    def mousePressEvent(self, event):
        if event.modifiers() == Qt.AltModifier:
            cursor = self.cursorForPosition(event.pos())
            self.extra_cursors.append(cursor)
            self.highlightCurrentLine()
            return
        else:
            if self.extra_cursors:
                self.extra_cursors.clear()
                self.highlightCurrentLine()
            super().mousePressEvent(event)

    def focusInEvent(self, e):
        if self._completer:
            self._completer.setWidget(self)
        super().focusInEvent(e)

    def keyPressEvent(self, e):
        # Monaco shortcuts
        if e.modifiers() == (Qt.AltModifier | Qt.ShiftModifier):
            if e.key() == Qt.Key_Up:
                self.copy_line_up()
                return
            elif e.key() == Qt.Key_Down:
                self.copy_line_down()
                return
        elif e.modifiers() == Qt.AltModifier:
            if e.key() == Qt.Key_Up:
                self.move_line_up()
                return
            elif e.key() == Qt.Key_Down:
                self.move_line_down()
                return

        if self._completer and self._completer.popup().isVisible():
            if e.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                e.ignore()
                return

        # Multiple cursors typing
        if self.extra_cursors:
            if e.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right) and not e.modifiers() & Qt.ShiftModifier:
                self.extra_cursors.clear()
                self.highlightCurrentLine()
            elif e.text() or e.key() in (Qt.Key_Backspace, Qt.Key_Delete, Qt.Key_Return, Qt.Key_Enter):
                main_cursor = self.textCursor()
                main_cursor.beginEditBlock()
                
                # type at extra cursors
                for cursor in self.extra_cursors:
                    if e.key() == Qt.Key_Backspace:
                        cursor.deletePreviousChar()
                    elif e.key() == Qt.Key_Delete:
                        cursor.deleteChar()
                    elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
                        cursor.insertText('\n')
                    elif e.text():
                        cursor.insertText(e.text())
                        
                main_cursor.endEditBlock()
                self.highlightCurrentLine()

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

    def copy_line_up(self):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        line_text = cursor.selectedText()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.insertText(line_text + '\n')
        cursor.movePosition(QTextCursor.PreviousBlock)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def copy_line_down(self):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        line_text = cursor.selectedText()
        cursor.movePosition(QTextCursor.EndOfBlock)
        cursor.insertText('\n' + line_text)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def move_line_up(self):
        cursor = self.textCursor()
        if cursor.blockNumber() == 0:
            return
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor) # get the newline
        line_text = cursor.selectedText()
        cursor.removeSelectedText()
        cursor.movePosition(QTextCursor.PreviousBlock)
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.insertText(line_text)
        cursor.movePosition(QTextCursor.PreviousBlock)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def move_line_down(self):
        cursor = self.textCursor()
        if cursor.blockNumber() == self.blockCount() - 1:
            return
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        line_text = cursor.selectedText()
        
        # Remove current line
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        
        # Insert after next line
        cursor.movePosition(QTextCursor.EndOfBlock)
        cursor.insertText('\n' + line_text)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

