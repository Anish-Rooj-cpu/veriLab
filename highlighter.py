import re
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

class VerilogHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        # Monaco Colors
        self.fmt_keyword = QTextCharFormat()
        self.fmt_keyword.setForeground(QColor("#569CD6")) # Blue
        self.fmt_keyword.setFontWeight(QFont.Bold)
        
        self.fmt_type = QTextCharFormat()
        self.fmt_type.setForeground(QColor("#4EC9B0")) # Teal
        
        self.fmt_number = QTextCharFormat()
        self.fmt_number.setForeground(QColor("#B5CEA8")) # Light Green
        
        self.fmt_string = QTextCharFormat()
        self.fmt_string.setForeground(QColor("#CE9178")) # Orange
        
        self.fmt_comment = QTextCharFormat()
        self.fmt_comment.setForeground(QColor("#6A9955")) # Green
        
        # Rainbow bracket colors
        self.rainbow_colors = [
            QColor("#FFD700"), # Gold
            QColor("#DA70D6"), # Orchid
            QColor("#179FFF")  # Light Blue
        ]
        self.rainbow_fmts = []
        for c in self.rainbow_colors:
            fmt = QTextCharFormat()
            fmt.setForeground(c)
            fmt.setFontWeight(QFont.Bold)
            self.rainbow_fmts.append(fmt)
            
        # Basic regexes
        self.types_re = re.compile(r'\b(logic|bit|byte|shortint|int|longint|string)\b')
        self.keywords_re = re.compile(r'\b(always|and|assign|default|defparam|disable|edge|else|for|force|forever|fork|if|initial|inout|input|integer|join|macromodule|nand|negedge|nor|not|or|output|parameter|posedge|reg|release|repeat|supply0|supply1|time|tran|tranif0|tranif1|tri|tri0|tri1|triand|trior|trireg|vectored|wait|wand|while|wire|wor|xnor|xor)\b')
        self.number_re = re.compile(r"\b\d+'[bBoOdDhH][0-9a-fA-F_xXzZ]+\b|\b\d+\b")
        
        # Rainbow regexes
        self.inc_re = re.compile(r'\b(module|begin|case|casex|casez|generate|function|task|class)\b|\(|\{|\[')
        self.dec_re = re.compile(r'\b(endmodule|end|endcase|endgenerate|endfunction|endtask|endclass)\b|\)|\}|\]')
        
        self.block_comment_end_re = re.compile(r'\*/')

        self.token_re = re.compile(
            r'/\*|'                                           # Block comment start
            r'\*/|'                                           # Block comment end
            r'//.*|'                                          # Line comment
            r'"[^"\\]*(\\.[^"\\]*)*"|'                        # String
            r'\b(?:module|begin|case|casex|casez|generate|function|task|class|'
            r'endmodule|end|endcase|endgenerate|endfunction|endtask|endclass)\b|'  # Rainbow keywords
            r'[\(\)\[\]\{\}]'                                 # Rainbow brackets
        )

    def highlightBlock(self, text):
        prev_state = self.previousBlockState()
        if prev_state == -1:
            prev_state = 0
            
        in_multiline = prev_state & 1
        depth = prev_state >> 1
        
        # 1. Apply basic types and numbers globally first
        for m in self.types_re.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_type)
        for m in self.keywords_re.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_keyword)
        for m in self.number_re.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_number)
            
        # 2. Tokenize left-to-right to override with strings/comments and apply rainbow brackets
        pos = 0
        while pos < len(text):
            if in_multiline:
                end_match = self.block_comment_end_re.search(text, pos)
                if end_match:
                    length = end_match.end() - pos
                    self.setFormat(pos, length, self.fmt_comment)
                    in_multiline = 0
                    pos = end_match.end()
                else:
                    self.setFormat(pos, len(text) - pos, self.fmt_comment)
                    pos = len(text)
                continue
                
            m = self.token_re.search(text, pos)
            if not m:
                break
                
            token = m.group(0)
            start = m.start()
            end = m.end()
            length = end - start
            
            if token == '/*':
                in_multiline = 1
                pos = start
                continue
                
            elif token.startswith('//'):
                self.setFormat(start, length, self.fmt_comment)
                
            elif token.startswith('"'):
                self.setFormat(start, length, self.fmt_string)
                
            elif token == '*/':
                # Stray end comment, just ignore or format as comment
                self.setFormat(start, length, self.fmt_comment)
                
            else:
                # Rainbow bracket / block keyword
                is_inc = self.inc_re.fullmatch(token)
                is_dec = self.dec_re.fullmatch(token)
                
                if is_dec:
                    depth = max(0, depth - 1)
                    fmt = self.rainbow_fmts[depth % len(self.rainbow_fmts)]
                    self.setFormat(start, length, fmt)
                elif is_inc:
                    fmt = self.rainbow_fmts[depth % len(self.rainbow_fmts)]
                    self.setFormat(start, length, fmt)
                    depth += 1
                    
            pos = end
            
        self.setCurrentBlockState((depth << 1) | in_multiline)
