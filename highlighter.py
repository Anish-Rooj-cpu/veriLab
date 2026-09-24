from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

class VerilogHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlightingRules = []

        # Keyword format
        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#569CD6")) # Blue
        keywordFormat.setFontWeight(QFont.Bold)

        keywords = [
            "always", "and", "assign", "begin", "case", "casex", "casez", "default", "defparam",
            "disable", "edge", "else", "end", "endcase", "endmodule", "endfunction", "endgenerate",
            "endtask", "for", "force", "forever", "fork", "function", "generate", "if", "initial",
            "inout", "input", "integer", "join", "macromodule", "module", "nand", "negedge", "nor",
            "not", "or", "output", "parameter", "posedge", "reg", "release", "repeat", "supply0",
            "supply1", "task", "time", "tran", "tranif0", "tranif1", "tri", "tri0", "tri1", "triand",
            "trior", "trireg", "vectored", "wait", "wand", "while", "wire", "wor", "xnor", "xor"
        ]
        
        for word in keywords:
            pattern = QRegExp(r'\b' + word + r'\b')
            self.highlightingRules.append((pattern, keywordFormat))

        # Types format (like logic, bit in SystemVerilog, but we'll highlight them differently if needed)
        typeFormat = QTextCharFormat()
        typeFormat.setForeground(QColor("#4EC9B0")) # Teal
        
        types = ["logic", "bit", "byte", "shortint", "int", "longint", "string"]
        for word in types:
            pattern = QRegExp(r'\b' + word + r'\b')
            self.highlightingRules.append((pattern, typeFormat))

        # Number format
        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) # Light green
        self.highlightingRules.append((QRegExp(r"\b\d+'[bBoOdDhH][0-9a-fA-F_xXzZ]+\b"), numberFormat))
        self.highlightingRules.append((QRegExp(r"\b\d+\b"), numberFormat))

        # String format
        self.stringFormat = QTextCharFormat()
        self.stringFormat.setForeground(QColor("#CE9178")) # Orange/Brown
        self.highlightingRules.append((QRegExp(r'".*"'), self.stringFormat))

        # Single line comment format
        self.commentFormat = QTextCharFormat()
        self.commentFormat.setForeground(QColor("#6A9955")) # Green
        self.highlightingRules.append((QRegExp(r"//[^\n]*"), self.commentFormat))

        # Multi-line comment format
        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(QColor("#6A9955"))
        self.commentStartExpression = QRegExp(r"/\*")
        self.commentEndExpression = QRegExp(r"\*/")

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        startIndex = 0
        if self.previousBlockState() != 1:
            startIndex = self.commentStartExpression.indexIn(text)

        while startIndex >= 0:
            endIndex = self.commentEndExpression.indexIn(text, startIndex)
            commentLength = 0
            if endIndex == -1:
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
            else:
                commentLength = endIndex - startIndex + self.commentEndExpression.matchedLength()
            
            self.setFormat(startIndex, commentLength, self.multiLineCommentFormat)
            startIndex = self.commentStartExpression.indexIn(text, startIndex + commentLength)
