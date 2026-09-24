import re

def format_verilog(code):
    lines = code.split('\n')
    formatted = []
    
    indent = 0
    in_comment = False
    
    dec_re = re.compile(r'\b(endmodule|end|endcase|endgenerate|endtask|endfunction|endclass|endpackage|endinterface)\b')
    inc_re = re.compile(r'\b(module|begin|case|casex|casez|generate|macromodule|task|function|class|package|interface)\b')
    
    for line in lines:
        s = line.strip()
        
        if in_comment:
            formatted.append(('    ' * indent) + s)
            if '*/' in s:
                in_comment = False
            continue
            
        if s.startswith('/*') and '*/' not in s:
            in_comment = True
            formatted.append(('    ' * indent) + s)
            continue
            
        code_part = s
        if '//' in s:
            code_part = s.split('//')[0].strip()
        if '/*' in s:
            code_part = s.split('/*')[0].strip()
            
        decrements = len(dec_re.findall(code_part))
        increments = len(inc_re.findall(code_part))
        
        starts_with_dec = False
        if code_part:
            words = [w for w in re.split(r'\W+', code_part) if w]
            if words and dec_re.match(words[0]):
                starts_with_dec = True
                
        temp_indent = indent
        if starts_with_dec:
            temp_indent = max(0, indent - decrements) # use decrements just to be safe if multiple ends
            if temp_indent < 0: temp_indent = 0
            
        if s:
            formatted.append(('    ' * temp_indent) + s)
        else:
            formatted.append('')
            
        indent = max(0, indent + increments - decrements)
        
    return '\n'.join(formatted)

if __name__ == "__main__":
    import sys
    with open(sys.argv[1], "r", encoding="utf-8", errors="ignore") as f:
        print(format_verilog(f.read()))
