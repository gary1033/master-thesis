import os
import json
import re
import io
import numpy as np
import tokenize
from get_conditional_line import get_conditional_lines
import ast

def fix_relative_imports(code, package_name):
    def replace_relative(match):
        dots = match.group(1)
        module = match.group(2)
        levels = len(dots) - 1  # number of dots minus 1 (. is same level, .. is up 1 level, ...)
        pkgs = package_name.split('.')
        if levels > len(pkgs):
            # If going up too many levels, fallback to root
            new_pkg = module
        else:
            new_pkg = '.'.join(pkgs[:-levels] if levels else pkgs)
            if new_pkg:
                new_pkg = f'{new_pkg}.{module}'
            else:
                new_pkg = module
        return f'from {new_pkg}'

    # Replace from .module, from ..module, from ...module
    code = re.sub(r'from (\.+)(\w+)', replace_relative, code)
    # Replace from . import module
    code = re.sub(r'from \. import (\w+)', lambda m: f'from {package_name} import {m.group(1)}', code)
    return code
def remove_space(code):
    final_code = ""
    for line in code.split('\n'):
        if line.strip() != "":
            final_code += line + "\n"
    return final_code
def line_code(code):
    """Return a list of line numbers that contain actual logical code, excluding blank lines, imports, def, class, etc."""
    try:
        tree = ast.parse(code)
        lines = code.split('\n')
        line_numbers = []

        def collect_lines(node):
            """Collect line numbers from the node and its children"""
            if hasattr(node, 'lineno'):
                # Skip docstrings (Expr with Constant)
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    return
                # Skip import statements
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    return
                # Skip module-level variables (such as __author__, __all__, etc.)
                if isinstance(node, ast.Assign):
                    # Check whether this is a module-level variable
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.startswith('__'):
                            return
                        # Skip other module-level variables
                        if isinstance(target, ast.Name) and target.id in ['__author__', '__all__', '__version__', '__doc__']:
                            return
                # Skip function/class definitions (only take their bodies)
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    # Only take the function/class body, not the def/class line
                    for child in node.body:
                        collect_lines(child)
                    return
                # Skip pass, break, continue
                if isinstance(node, (ast.Pass, ast.Break, ast.Continue)):
                    return
                # Skip plain return (no value)
                if isinstance(node, ast.Return) and node.value is None:
                    return

                # Take nodes that contain real logic:
                # - Assignment (Assign): variables, constants
                # - Augmented assignment (AugAssign): +=, -=, etc.
                # - Function calls (Call)
                # - Expressions (Expr) that are not docstrings
                # - If, For, While, Try, With statements
                # - Raise, Assert statements
                if isinstance(node, (ast.Assign, ast.AugAssign, ast.Call, ast.If,
                                   ast.For, ast.While, ast.Try, ast.With, ast.Raise,
                                   ast.Assert, ast.Delete, ast.Global, ast.Nonlocal, ast.Return)):
                    line_numbers.append(node.lineno)
                elif isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
                    # Expr that is not a docstring (may be a function call, etc.)
                    line_numbers.append(node.lineno)

            # Traverse children
            for child in ast.iter_child_nodes(node):
                collect_lines(child)

        collect_lines(tree)

        # Deduplicate and sort
        line_numbers = sorted(list(set(line_numbers)))

        # Filter out additional invalid lines
        filtered_lines = []
        for line_num in line_numbers:
            if line_num <= len(lines):
                line = lines[line_num - 1].strip()
                # Skip blank lines, comments, imports, def, class
                if (line and
                    not line.startswith('#') and
                    not line.startswith('import ') and
                    not line.startswith('from ') and
                    not line.startswith('def ') and
                    not line.startswith('class ') and
                    not line.startswith('@') and
                    line != 'pass' and
                    line not in ['else:', 'except:', 'finally:', 'elif:'] and
                    line not in ['{', '}', '[', ']', '(', ')']):
                    filtered_lines.append(line_num)

        return filtered_lines

    except (SyntaxError, IndentationError):
        # Fallback if AST parsing fails
        lines = code.split('\n')
        line_numbers = []
    
        i = 0
        in_docstring = False
        docstring_delim = None
            
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Skip blank lines
            if not stripped:
                i += 1
                continue

            # Skip comments
            if stripped.startswith('#'):
                i += 1
                continue

            # Handle docstring - IMPROVED SECTION
            if not in_docstring:
                # Check single-line docstring
                if (stripped.startswith('"""') and stripped.endswith('"""') and len(stripped) > 3) or \
                (stripped.startswith("'''") and stripped.endswith("'''") and len(stripped) > 3):
                    i += 1
                    continue
                # Check start of multi-line docstring
                elif stripped.startswith('"""') and not stripped.endswith('"""'):
                    in_docstring = True
                    docstring_delim = '"""'
                    i += 1
                    continue
                elif stripped.startswith("'''") and not stripped.endswith("'''"):
                    in_docstring = True
                    docstring_delim = "'''"
                    i += 1
                    continue
            else:
                # Inside docstring - SKIP ALL LINES INSIDE DOCSTRING
                if docstring_delim and docstring_delim in stripped:
                    # Found end of docstring
                    in_docstring = False
                    docstring_delim = None
                i += 1
                continue

            # Skip import statements
            if stripped.startswith('import ') or stripped.startswith('from '):
                i += 1
                continue

            # Skip def, class declarations (only take function/class body)
            if stripped.startswith('def ') or stripped.startswith('class '):
                i += 1
                continue

            # Skip decorators
            if stripped.startswith('@'):
                i += 1
                continue

            # Skip pass statements
            if stripped == 'pass':
                i += 1
                continue

            # Skip simple return statements
            if stripped == 'return' or stripped == 'return None':
                i += 1
                continue

            # Skip plain else:, except:, finally:
            if stripped in ['else:', 'except:', 'finally:', 'elif:']:
                i += 1
                continue

            # Skip lines that contain only brackets
            if stripped in ['{', '}', '[', ']', '(', ')']:
                i += 1
                continue

            # Check whether this is a continuation of the previous statement
            current_indent = len(line) - len(line.lstrip())

            # Check whether the previous line ends with comma, open bracket, or backslash
            is_continuation = False
            if i > 0:
                prev_line = lines[i-1].strip()
                prev_indent = len(lines[i-1]) - len(lines[i-1].lstrip())

                # Consider it a continuation only if:
                # 1. Previous line ends with a continuation char and current line has larger indent
                # 2. Or current line has significantly larger indent (belongs to a nested block)
                if ((prev_line.endswith(',') or
                    prev_line.endswith('(') or
                    prev_line.endswith('[') or
                    prev_line.endswith('{') or
                    prev_line.endswith('\\')) and
                    current_indent > prev_indent):
                    is_continuation = True

            # If this is the first line of a statement or a line with real logic
            # (not a continuation line)
            if not is_continuation:
                # Add this line to results
                line_numbers.append(i + 1)

            i += 1

    return line_numbers
def extract_class_names(code: str):
    """
    Return a list of all class names in the given code.
    """
    try:
        # Try direct parse
        tree = ast.parse(code)
        class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        return class_names
    except (IndentationError, SyntaxError):
        # If there is an indentation error, try to fix by normalizing indentation
        try:
            # Normalize indentation - remove invalid indentation
            lines = code.split('\n')
            normalized_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped:
                    # Find a valid indentation level
                    indent_level = 0
                    for char in line:
                        if char == ' ':
                            indent_level += 1
                        elif char == '\t':
                            indent_level += 4  # Convert tab to spaces
                        else:
                            break
                    # Normalize to 4 spaces per level
                    normalized_indent = '    ' * (indent_level // 4)
                    normalized_lines.append(normalized_indent + stripped)
                else:
                    normalized_lines.append('')

            normalized_code = '\n'.join(normalized_lines)
            tree = ast.parse(normalized_code)
            class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            return class_names
        except (IndentationError, SyntaxError):
            # If it still fails, return an empty list
            return []
def remove_external_imports(code: str) -> str:
    """
    Remove all import and from ... import ... lines from Python code.
    """
    lines = code.splitlines()
    filtered = []
    for line in lines:
        stripped = line.strip()
        # Remove import or from ... import ... lines
        if stripped.startswith('import ') or stripped.startswith('from '):
            continue
        filtered.append(line)
    return '\n'.join(filtered)
def find_enclosing_def_class(code: str, lineno: int):
    """
    Return a tuple (class_name, func_name) that encloses the line `lineno` in the code.
    Return None if it is not inside any class or function.
    """
    tree = ast.parse(code)
    class_name = None
    func_name = None

    def visit(node, parents):
        nonlocal class_name, func_name
        # Check whether the node covers the target line
        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            if node.lineno <= lineno <= node.end_lineno:
                if isinstance(node, ast.ClassDef):
                    class_name = node.name
                if isinstance(node, ast.FunctionDef):
                    func_name = node.name
        for child in ast.iter_child_nodes(node):
            visit(child, parents + [node])

    # First, assign end_lineno to nodes if using Python <3.8
    ast.increment_lineno(tree, 0)
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            if not hasattr(child, 'end_lineno'):
                child.end_lineno = getattr(child, 'lineno', None)

    visit(tree, [])
    return class_name, func_name
def fix_line_breaks_in_code(code: str) -> str:
    """
    Remove all comments (including docstrings), then merge code lines that were unreasonably split across lines, including long expressions inside parentheses ((), [], {}).
    Example:
    return (
        a or
        b
    )
    => return (a or b)
    """
    import re
    # Remove docstrings ("""...""" or '''...''')
    code = re.sub(r'"""[\s\S]*?"""', '', code)
    code = re.sub(r"'''[\s\S]*?'''", '', code)
    # Remove trailing-of-line comments and comment-only lines
    code_no_comment = []
    for line in code.split('\n'):
        # Drop comment-only or empty lines
        if re.match(r'^\s*#', line) or line.strip() == '':
            continue
        # Remove trailing comment (not inside a string)
        # Simple: split on the first # that is not inside a string
        def remove_inline_comment(s):
            in_single = in_double = False
            for i, c in enumerate(s):
                if c == '"' and not in_single:
                    in_double = not in_double
                elif c == "'" and not in_double:
                    in_single = not in_single
                elif c == '#' and not in_single and not in_double:
                    return s[:i].rstrip()
            return s
        code_no_comment.append(remove_inline_comment(line))
    code = '\n'.join(code_no_comment)

    lines = code.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        # If the line starts with an open bracket or has an unclosed open bracket
        if re.search(r'\($|\[$|\{$', line.strip()) or (
            line.count('(') > line.count(')') or
            line.count('[') > line.count(']') or
            line.count('{') > line.count('}')
        ):
            open_paren = line.count('(') - line.count(')')
            open_brack = line.count('[') - line.count(']')
            open_brace = line.count('{') - line.count('}')
            expr = line.strip()
            j = i + 1
            while j < len(lines) and (open_paren > 0 or open_brack > 0 or open_brace > 0):
                next_line = lines[j].strip()
                expr += ' ' + next_line
                open_paren += next_line.count('(') - next_line.count(')')
                open_brack += next_line.count('[') - next_line.count(']')
                open_brace += next_line.count('{') - next_line.count('}')
                j += 1
            fixed_lines.append(expr)
            i = j
        else:
            # Merge condition lines that were unreasonably split
            while i + 1 < len(lines):
                next_line = lines[i + 1].lstrip()
                if re.match(r'^(and|or|else|elif|except|finally|\)|\]|\}|[+\-*/%&|^.,:<>!=])', next_line):
                    line += ' ' + next_line
                    i += 1
                else:
                    break
            fixed_lines.append(line)
            i += 1
    return '\n'.join(fixed_lines)

# Example usage


def find_path_from_target_to_root(code, target_lineno):
    """
    Return a list of line numbers (lineno) from the node with target_lineno up to the AST root.
    Returns None if no node has lineno == target_lineno.
    """
    tree = ast.parse(code)
    parent_map = {}
    target_node = None

    # Walk the tree to build parent_map and find the target node
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent_map[child] = node
        if hasattr(node, 'lineno') and node.lineno == target_lineno:
            target_node = node

    if target_node is None:
        return None

    # Trace from target_node up to root
    path = []
    node = target_node
    while node in parent_map:
        if hasattr(node, 'lineno'):
            path.append(node.lineno)
        node = parent_map[node]
    # Add the root if it has a lineno
    if hasattr(node, 'lineno'):
        path.append(node.lineno)
    return path[::-1]  # Path from root to target

def similarity(a,b):
    """Compute similarity between two lists."""
    # Handle the case where a or b is None
    if a is None or b is None:
        return 0.0
    
    a_set = set(a)
    b_set = set(b)
    test_good = None
    execution_good = None
    intersection = a_set.intersection(b_set)
    
    # Avoid division by zero
    if len(b_set) == 0:
        return 0.0
    
    return len(intersection) / len(b_set)
def find_closest_test(result_execute, target_line, python_code):
    condition = get_conditional_lines(python_code, target_line)
    print(condition)
    for x in condition[::-1]:
        for _, item in enumerate(result_execute):
            if x in item['executed_lines']:
                return item['test']
    
    return result_execute[np.random.randint(0, len(result_execute))]['test']
    
# def solve1(result_execute, code, target_line):
#     max_threhold = 0
#     path_target = find_path_from_target_to_root(code, target_line)
#     test_good = None
#     best = None
#     execution_good = None
    
#     # Handle the case where path_target is None
#     if path_target is None:
#         return None, None, None, 0.0
    
#     for i, item in enumerate(result_execute):
#         simi = similarity(item['executed_lines'], path_target)
#         if simi >= max_threhold:
#             best = i
#             max_threhold = simi 
#             test_good = item['test']
#             execution_good = item['executed_lines']
#     return best, test_good, execution_good, max_threhold

def extract_python_code_block(text):
    # Find the code block inside ```python ... ```
    if text is None:   # None-guard: LLM may return content=None on length cap, refusal, or 5xx
        return ""
    pattern = r"```python\s*([\s\S]*?)```"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return ""
def extract_line(code, line):
    code_line = code.split('\n')
    return code_line[line-1]

def extract_test_func(code, func_name):
    # Search from def test_func_name() to end of file or to a non-indented line
    pattern = rf"(def test_{func_name}\s*\([\s\S]*?)(?=^def |\Z)"
    match = re.search(pattern, code, re.MULTILINE)
    test_func = ""
    if match:
        test_func = match.group(1).strip()
    # Find the line that calls the test outside (not inside a function body)
    lines = code.splitlines()
    call_line = f"{func_name}()"
    call_found = False
    for line in lines:
        if line.strip() == call_line:
            call_found = True
            break
    if call_found and not test_func.endswith(call_line):
        test_func += "\n" + call_line
    return test_func

def seg_code_divide_class(code: str):
    """
    Return a list of class code blocks (as strings) from the input code.
    """
    try:
        tree = ast.parse(code)
        class_segments = []
        lines = code.splitlines(keepends=True)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                start = node.lineno - 1
                # Find the class end line (use node.end_lineno if available, otherwise search manually)
                end = getattr(node, 'end_lineno', None)
                if end is None:
                    # If Python <3.8 lacks end_lineno, search manually
                    # Take all lines until a class/def at the same level or end of file
                    end = start + 1
                    indent = len(lines[start]) - len(lines[start].lstrip())
                    for i in range(start + 1, len(lines)):
                        line = lines[i]
                        if line.strip() == "":
                            continue
                        if len(line) - len(line.lstrip()) <= indent and (line.lstrip().startswith('class ') or line.lstrip().startswith('def ')):
                            break
                        end = i + 1
                class_code = ''.join(lines[start:end])
                class_segments.append(class_code)
        return class_segments
    except (IndentationError, SyntaxError) as e:
        # If parsing fails, return an empty list
        print(f"Warning: Cannot parse code for class segmentation: {e}")
        return []

def read_jsonl(path):
    data=[]
    with open(path,'r') as f:
        for line in f:
            data.append(json.loads(line))
    return data
def code_in_line(code):
    """Add line numbers to code."""
    lines=code.split('\n')
    new_code=''
    for i, line in enumerate(lines):
        new_code+=f'{i+1}. {line}\n'
    return new_code
def extract(code, target_line):
    code = code_in_line(code)
    final_code = ''
    for i, line in enumerate(code.split('\n')):
        if i == target_line:
            return final_code
        final_code+=f'{line}\n'
    return final_code

def reform_code_lines_fixed(code: str) -> str:

    import re

    lines = code.split('\n')
    reformed_lines = []
    buffer = ''
    paren_count = 0
    in_docstring = False
    docstring_delim = None

    def remove_inline_comment(s):
        in_single = in_double = False
        for i, c in enumerate(s):
            if c == '"' and not in_single:
                in_double = not in_double
            elif c == "'" and not in_double:
                in_single = not in_single
            elif c == '#' and not in_single and not in_double:
                return s[:i].rstrip()
        return s

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        indent = line[:len(line) - len(stripped)]

        # Handle docstring
        if not in_docstring:
            if (stripped.startswith('"""') or stripped.startswith("'''")):
                in_docstring = True
                docstring_delim = stripped[:3]
                if buffer:
                    reformed_lines.append(buffer)
                    buffer = ''
                    paren_count = 0
                reformed_lines.append(line)
                i += 1
                continue
        else:
            reformed_lines.append(line)
            # End of docstring
            if docstring_delim and docstring_delim in stripped and len(stripped) > 3:
                in_docstring = False
                docstring_delim = None
            elif docstring_delim and stripped.endswith(docstring_delim):
                in_docstring = False
                docstring_delim = None
            i += 1
            continue

        # If it is a comment, flush the buffer and keep the comment as-is
        if re.match(r'^\s*#', line):
            if buffer:
                reformed_lines.append(buffer)
                buffer = ''
                paren_count = 0
            reformed_lines.append(line)
            i += 1
            continue
        # Skip blank lines
        if not stripped:
            if buffer:
                reformed_lines.append(buffer)
                buffer = ''
                paren_count = 0
            reformed_lines.append('')
            i += 1
            continue
        # Check whether this is really a continuation
        is_continuation = False
        if buffer:
            prev_stripped = buffer.rstrip()
            # If the previous line ends with a line continuation (\ or \\)
            if prev_stripped.endswith('\\') or prev_stripped.endswith('\\\\'):
                buffer = buffer.rstrip('\\').rstrip()
                is_continuation = True
            elif paren_count > 0:
                is_continuation = True
            elif (prev_stripped.endswith(('(', '[', '{', ',')) and 
                  not stripped.startswith(('def ', 'class ', 'if ', 'for ', 'while ', 'try ', 'with '))):
                is_continuation = True
            elif (prev_stripped.endswith(('+', '-', '*', '/', '%', '//', '**', '&', '|', '^', '<<', '>>')) and
                  not stripped.startswith(('def ', 'class ', 'if ', 'for ', 'while ', 'try ', 'with '))):
                is_continuation = True
        if buffer and not is_continuation:
            reformed_lines.append(buffer)
            buffer = ''
            paren_count = 0
        if is_continuation:
            buffer += ' ' + remove_inline_comment(stripped)
        else:
            buffer = indent + remove_inline_comment(stripped)
        paren_count = buffer.count('(') + buffer.count('[') + buffer.count('{') - buffer.count(')') - buffer.count(']') - buffer.count('}')
        i += 1
    if buffer:
        reformed_lines.append(buffer)
    return '\n'.join(reformed_lines)
def re_format_line(code):
    line_run = line_code(code)
    final_line = []
    prev = -1
    for x in line_run:
        if prev == -1:
            prev = x
            final_line.append(x)
        else:
            if x == prev+1:
                if get_conditional_lines(code,x) == get_conditional_lines(code,prev) or (len(get_conditional_lines(code,x))>0 and get_conditional_lines(code,x)[-1] == prev):
                    prev = x
                    continue
                else:
                    final_line.append(x)
                    prev = x
            else:
                final_line.append(x)
                prev = x
    return final_line
def write_jsonl(data,path):
    with open(path,'w') as f:
        for d in data:
            f.write(json.dumps(d)+'\n')
def line_code_option2(code):
    """Return a list of line numbers that contain actual logical code, excluding blank lines, imports, def, class, etc."""
    try:
        tree = ast.parse(code)
        lines = code.split('\n')
        line_numbers = []
        
        def collect_lines(node):
            """Collect line numbers from the node and its children"""
            if hasattr(node, 'lineno'):
                # Skip docstrings (Expr with Constant)
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    return
                # Skip import statements
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    return
                # Skip module-level variables (such as __author__, __all__, etc.)
                if isinstance(node, ast.Assign):
                    # Check whether this is a module-level variable
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.startswith('__'):
                            return
                        # Skip other module-level variables
                        if isinstance(target, ast.Name) and target.id in ['__author__', '__all__', '__version__', '__doc__']:
                            return
                # Skip function/class definitions (only take their bodies)
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    # Only take the function/class body, not the def/class line
                    for child in node.body:
                        collect_lines(child)
                    return
                # Skip pass, break, continue
                if isinstance(node, (ast.Pass, ast.Break, ast.Continue)):
                    return
                # Skip plain return
                if isinstance(node, ast.Return) and (node.value is None or 
                    (isinstance(node.value, ast.Name) and node.value.id == 'None')):
                    return
                
                # Take nodes that contain real logic:
                # - Assignment (Assign): variables, constants
                # - Augmented assignment (AugAssign): +=, -=, etc.
                # - Function calls (Call)
                # - Expressions (Expr) that are not docstrings
                # - If, For, While, Try, With statements
                # - Raise, Assert statements
                if isinstance(node, (ast.Assign, ast.AugAssign, ast.Call, ast.If, 
                                   ast.For, ast.While, ast.Try, ast.With, ast.Raise, 
                                   ast.Assert, ast.Delete, ast.Global, ast.Nonlocal)):
                    line_numbers.append(node.lineno)
                elif isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
                    # Expr that is not a docstring (may be a function call, etc.)
                    line_numbers.append(node.lineno)
            
            # Traverse children
            for child in ast.iter_child_nodes(node):
                collect_lines(child)
        
        collect_lines(tree)
        
        # Deduplicate and sort
        line_numbers = sorted(list(set(line_numbers)))
        
        # Filter out additional invalid lines
        filtered_lines = []
        for line_num in line_numbers:
            if line_num <= len(lines):
                line = lines[line_num - 1].strip()
                # Skip blank lines, comments, imports, def, class
                if (line and 
                    not line.startswith('#') and 
                    not line.startswith('import ') and 
                    not line.startswith('from ') and
                    not line.startswith('def ') and 
                    not line.startswith('class ') and
                    not line.startswith('@') and
                    line != 'pass' and
                    line not in ['else:', 'except:', 'finally:', 'elif:'] and
                    line not in ['{', '}', '[', ']', '(', ')']):
                    filtered_lines.append(line_num)
        
        return filtered_lines
        
    except (SyntaxError, IndentationError):
        # Fallback if AST parsing fails
        lines = code.split('\n')
        line_numbers = []
    
        i = 0
        in_docstring = False
        docstring_delim = None
            
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Skip blank lines
            if not stripped:
                i += 1
                continue
                
            # Skip comments
            if stripped.startswith('#'):
                i += 1
                continue
                
                # Handle docstring
                if not in_docstring:
                    # Check single-line docstring
                    if (stripped.startswith('"""') and stripped.endswith('"""') and len(stripped) > 3) or \
                    (stripped.startswith("'''") and stripped.endswith("'''") and len(stripped) > 3):
                        i += 1
                        continue
                    # Check start of multi-line docstring
                    elif stripped.startswith('"""') and not stripped.endswith('"""'):
                        in_docstring = True
                        docstring_delim = '"""'
                        i += 1
                        continue
                    elif stripped.startswith("'''") and not stripped.endswith("'''"):
                        in_docstring = True
                        docstring_delim = "'''"
                        i += 1
                        continue
                else:
                    # Đang trong docstring
                    if docstring_delim and docstring_delim in stripped:
                        in_docstring = False
                        docstring_delim = None
                i += 1
                continue
                
            # Skip import statements
            if stripped.startswith('import ') or stripped.startswith('from '):
                i += 1
                continue
                
            # Skip def, class declarations (only take function/class body)
            if stripped.startswith('def ') or stripped.startswith('class '):
                i += 1
                continue
                
            # Skip decorators
            if stripped.startswith('@'):
                i += 1
                continue
                
            # Skip pass statements
            if stripped == 'pass':
                i += 1
                continue
                
            # Skip simple return statements
            if stripped == 'return' or stripped == 'return None':
                i += 1
                continue
                
            # Skip plain else:, except:, finally:
            if stripped in ['else:', 'except:', 'finally:', 'elif:']:
                i += 1
                continue
                
            # Skip lines that contain only brackets
            if stripped in ['{', '}', '[', ']', '(', ')']:
                i += 1
                continue
            
            # Check whether this is a continuation of the previous statement
            current_indent = len(line) - len(line.lstrip())

            # Check whether the previous line ends with comma, open bracket, or backslash
            is_continuation = False
            if i > 0:
                prev_line = lines[i-1].strip()
                prev_indent = len(lines[i-1]) - len(lines[i-1].lstrip())

                # Consider it a continuation only if:
                # 1. Previous line ends with a continuation char and current line has larger indent
                # 2. Or current line has significantly larger indent (belongs to a nested block)
                if ((prev_line.endswith(',') or
                    prev_line.endswith('(') or
                    prev_line.endswith('[') or
                    prev_line.endswith('{') or
                    prev_line.endswith('\\')) and
                    current_indent > prev_indent):
                    is_continuation = True

            # If this is the first line of a statement or a line with real logic
            # (not a continuation line)
            if not is_continuation:
                # Add this line to results
                line_numbers.append(i + 1)
            
            i += 1
    
    return line_numbers

def add_lineno(code):
    """Add line numbers to code."""
    lines=code.split('\n')
    new_code=''
    for i, line in enumerate(lines):
        new_code+=f'{i+1}. {line}\n'
    return new_code

def remove_comments_and_docstrings(source: str) -> str:
    """
    Remove all comments (# lines) and docstrings from Python code.
    """
    io_obj = io.StringIO(source)
    out = ""
    prev_toktype = tokenize.INDENT
    last_lineno = -1
    last_col = 0
    try:
        for tok in tokenize.generate_tokens(io_obj.readline):
            token_type = tok.type
            token_string = tok.string
            start_line, start_col = tok.start
            end_line, end_col = tok.end

            if start_line > last_lineno:
                last_col = 0
            if start_col > last_col:
                out += " " * (start_col - last_col)
            # Skip comments and docstrings
            if token_type == tokenize.COMMENT:
                pass
            elif token_type == tokenize.STRING:
                if prev_toktype != tokenize.INDENT and prev_toktype != tokenize.NEWLINE:
                    out += token_string
            else:
                out += token_string
            prev_toktype = token_type
            last_col = end_col
            last_lineno = end_line
    except Exception as e:
        # If error, return the original code
        return source
    return out
def add_lineno_comment(code,docstring_lines=None):
    """Add line numbers to code as comments."""
    lines=code.split('\n')
    for i in range(len(lines)-1,-1,-1):
        if lines[i]=='':
            lines.pop(i)
        else:
            break
    new_code=''
    if docstring_lines is None:
        for i, line in enumerate(lines):
            if i == len(lines) - 1:
                new_code+=f'{line}  #{i+1}'
            else:
                new_code+=f'{line}  #{i+1}\n'
    else:
        docstart,docend=docstring_lines
        for i, line in enumerate(lines):
            if i>=docstart and i<=docend:
                new_code+=f'{line}\n'
            else:
                if i == len(lines) - 1:
                    new_code+=f'{line}  #{i+1}'
                else:
                    new_code+=f'{line}  #{i+1}\n'
    return new_code
def get_filepath_from_import(import_line):
    import sys
    import importlib.util
    import_line = import_line.strip()
    if import_line.startswith('from '):
        # from ansible.executor.task_queue_manager import TaskQueueManager
        parts = import_line.replace('from ', '').replace('import ', ',').split(',')
        module_path = parts[0].strip()
        symbol = parts[1].strip() if len(parts) > 1 else None
    elif import_line.startswith('import '):
        # import ansible.executor.task_queue_manager
        module_path = import_line.replace('import ', '').strip()
        symbol = None
    else:
        return None, None, None

    # Skip standard or built-in modules
    try:
        spec = importlib.util.find_spec(module_path)
        if spec is None or spec.origin is None or module_path in sys.builtin_module_names:
            return None, module_path, symbol
    except (ValueError, ImportError, AttributeError):
        # Cases like inspect, abc... that have no __spec__ or raise other errors
        return None, module_path, symbol

    return spec.origin, module_path, symbol
def parse_import_tool(import_tool1):
    # If it is already a valid Python list
    try:
        result = ast.literal_eval(import_tool1)
        if isinstance(result, list):
            return result
    except Exception:
        pass

    # If it is a string like [import abc, import inspect] (no quotes)
    if import_tool1.strip().startswith('[') and 'import ' in import_tool1:
        # Add single quotes around each element
        import_tool1 = re.sub(
            r'\[([^\]]+)\]',
            lambda m: "[" + ", ".join(f"'{x.strip()}'" for x in m.group(1).split(',')) + "]",
            import_tool1
        )
        try:
            result = ast.literal_eval(import_tool1)
            if isinstance(result, list):
                return result
        except Exception:
            pass

    # If it is a string, split by line or by comma
    lines = [line.strip() for line in import_tool1.splitlines() if 'import ' in line]
    if not lines:
        # Try splitting by comma
        lines = [x.strip() for x in import_tool1.split(',') if 'import ' in x]
    return lines
def get_code_from_import_line(import_line):
    filepath, _, symbol = get_filepath_from_import(import_line)
    if not filepath or not os.path.exists(filepath):
        print("No file found for this import.")
        return None, None
    
    print(f"File path: {filepath}")
    
    # Try different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    code = None
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                code = f.read()
            break
        except UnicodeDecodeError:
            continue
    
    if code is None:
        print(f"Unable to read file with encodings: {encodings}")
        return None, None
    
    if symbol:
        # Find the specific class/function
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == symbol:
                    # Get the source code of the class/function
                    start_line = node.lineno - 1
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                    
                    lines = code.split('\n')
                    extracted_code = '\n'.join(lines[start_line:end_line])
                    
                    print(f"Found {type(node).__name__} '{symbol}':")
                    # print(extracted_code)
                    return filepath, extracted_code
        except SyntaxError:
            print("Unable to parse this file.")
    
    # If the specific symbol is not found, or there is no symbol, print the whole file
    # print("Code content:\n" + code)
    return filepath, code
def extract_external_import_lines(code):
    common_libs = {
        'os', 'sys', 'math', 're', 'json', 'datetime', 'time', 'random', 'collections',
        'itertools', 'functools', 'subprocess', 'threading', 'multiprocessing', 'logging',
        'unittest', 'doctest', 'argparse', 'shutil', 'glob', 'tempfile', 'pathlib', 'typing',
        'numpy', 'pandas', 'sklearn', 'matplotlib', 'scipy', 'torch', 'tensorflow', 'requests'
    }
    tree = ast.parse(code)
    lines = code.splitlines()
    results = []
    result1 = ''
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Get the line number (1-indexed)
            lineno = node.lineno - 1
            # Get the root module name
            if isinstance(node, ast.Import):
                mod = node.names[0].name.split('.')[0]
            else:
                mod = node.module.split('.')[0] if node.module else ''
            # Exclude modules starting with '__'
            if mod and not mod.startswith('__') and mod not in common_libs:
                results.append(lines[lineno].strip())
                result1 += f'{lines[lineno].strip()}\n'
    return result1
def line_code1(code):
    """Return a list of line numbers containing real logical code, but do NOT skip import, if, else, ... lines."""
    lines = code.split('\n')
    line_numbers = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Skip blank lines
        if not stripped:
            i += 1
            continue
        # Skip comments
        if stripped.startswith('#'):
            i += 1
            continue
        # Skip docstrings
        if stripped.startswith('"""') or stripped.startswith("'''"):
            i += 1
            continue
        # Skip decorators
        if stripped.startswith('@'):
            i += 1
            continue
        # Skip pass statements
        if stripped == 'pass':
            i += 1
            continue
        # Skip simple return statements
        if stripped == 'return' or stripped == 'return None':
            i += 1
            continue
        # Skip lines that contain only brackets
        if stripped in ['{', '}', '[', ']', '(', ')']:
            i += 1
            continue
        # Check whether this is a continuation of the previous statement
        current_indent = len(line) - len(line.lstrip())
        is_continuation = False
        if i > 0:
            prev_line = lines[i-1].strip()
            prev_indent = len(lines[i-1]) - len(lines[i-1].lstrip())
            if ((prev_line.endswith(',') or 
                 prev_line.endswith('(') or 
                 prev_line.endswith('[') or 
                 prev_line.endswith('{') or
                 prev_line.endswith('\\')) and 
                current_indent > prev_indent):
                is_continuation = True
        if not is_continuation:
            line_numbers.append(i + 1)
        i += 1
    return line_numbers

def reform_code_lines(code: str) -> str:
    import re
    lines = code.split('\n')
    reformed_lines = []
    buffer = ''
    buffer_indent = ''
    paren_count = 0

    def remove_inline_comment(s):
        in_single = in_double = False
        for i, c in enumerate(s):
            if c == '"' and not in_single:
                in_double = not in_double
            elif c == "'" and not in_double:
                in_single = not in_single
            elif c == '#' and not in_single and not in_double:
                return s[:i].rstrip()
        return s

    for idx, line in enumerate(lines):
        stripped = line.strip()
        indent = line[:len(line) - len(stripped)]
        # If it is a comment, flush the buffer (if any) and keep the comment as-is
        if re.match(r'^\s*#', line):
            if buffer:
                reformed_lines.append(buffer)
                buffer = ''
                buffer_indent = ''
                paren_count = 0
            reformed_lines.append(line)
            continue
        # Skip blank lines
        if not stripped:
            if buffer:
                reformed_lines.append(buffer)
                buffer = ''
                buffer_indent = ''
                paren_count = 0
            reformed_lines.append('')
            continue
        # Count open/close brackets to tell if still inside an unfinished expression
        open_paren = stripped.count('(') + stripped.count('[') + stripped.count('{')
        close_paren = stripped.count(')') + stripped.count(']') + stripped.count('}')
        # Check continuation: previous line ends with a continuation char or has unclosed brackets
        is_continuation = False
        if buffer:
            prev = buffer.rstrip()
            prev_paren_count = buffer.count('(') + buffer.count('[') + buffer.count('{') - buffer.count(')') - buffer.count(']') - buffer.count('}')
            if prev.endswith('\\') and not prev.endswith('\\\\'):
                reformed_lines.append(buffer)
                buffer = ''
                buffer_indent = ''
                paren_count = 0
                buffer = indent + remove_inline_comment(stripped)
                buffer_indent = indent
                paren_count = buffer.count('(') + buffer.count('[') + buffer.count('{') - buffer.count(')') - buffer.count(']') - buffer.count('}')
                continue
            elif (
                prev.endswith(('(', '[', '{', ',', '+', '-', '*', '/', '%', '<', '>', '==', '!=', '<=', '>=', '|', '&', '^', '~'))
                or prev_paren_count > 0
            ):
                is_continuation = True
        if buffer and not is_continuation:
            reformed_lines.append(buffer)
            buffer = ''
            buffer_indent = ''
            paren_count = 0
        if is_continuation:
            buffer += ' ' + remove_inline_comment(stripped)
        else:
            buffer = indent + remove_inline_comment(stripped)
            buffer_indent = indent
        paren_count = buffer.count('(') + buffer.count('[') + buffer.count('{') - buffer.count(')') - buffer.count(']') - buffer.count('}')
    if buffer:
        reformed_lines.append(buffer)
    return '\n'.join(reformed_lines)
def get_branch_arcs_ast(source: str):
    """
    Return a list of (from_line, to_line) pairs for branches of if/else/for/while/try/except/with.
    This is only approximate, not as complete as coverage.py.
    """
    tree = ast.parse(source)
    arcs = []

    for node in ast.walk(tree):
        # IF
        if isinstance(node, ast.If):
            if hasattr(node, 'lineno'):
                if node.body:
                    arcs.append((node.lineno, node.body[0].lineno))  # if True
                if node.orelse:
                    arcs.append((node.lineno, node.orelse[0].lineno))  # if False
        # FOR
        if isinstance(node, ast.For):
            if hasattr(node, 'lineno'):
                if node.body:
                    arcs.append((node.lineno, node.body[0].lineno))  # for body
                if node.orelse:
                    arcs.append((node.lineno, node.orelse[0].lineno))
        # WHILE
        if isinstance(node, ast.While):
            if hasattr(node, 'lineno'):
                if node.body:
                    arcs.append((node.lineno, node.body[0].lineno))  # while body
                if node.orelse:
                    arcs.append((node.lineno, node.orelse[0].lineno))
        # TRY
        if isinstance(node, ast.Try):
            if hasattr(node, 'lineno'):
                for handler in node.handlers:
                    if hasattr(handler, 'lineno'):
                        arcs.append((node.lineno, handler.lineno))
                if node.finalbody:
                    arcs.append((node.lineno, node.finalbody[0].lineno))
        # WITH
        if isinstance(node, (ast.With, ast.AsyncWith)):
            if hasattr(node, 'lineno') and node.body:
                arcs.append((node.lineno, node.body[0].lineno))
        # EXCEPT
        if isinstance(node, ast.ExceptHandler):
            if hasattr(node, 'lineno') and node.body:
                arcs.append((node.lineno, node.body[0].lineno))
        # MATCH (Python 3.10+)
        if hasattr(ast, 'Match') and isinstance(node, ast.Match):
            if hasattr(node, 'lineno'):
                for case in node.cases:
                    if hasattr(case, 'lineno'):
                        arcs.append((node.lineno, case.lineno))

    return arcs