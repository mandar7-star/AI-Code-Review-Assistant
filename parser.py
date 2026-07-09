import re
from typing import Dict, Any, List, Optional

class CodeParser:
    def __init__(self):
        pass
    
    def parse(self, code: str, language: str) -> Dict[str, Any]:
        """Parse code using regex-based parsing (works for all languages)"""
        language = language.lower()
        
        return {
            'language': language,
            'code': code,
            'lines': len(code.split('\n')),
            'functions': self._find_functions(code, language),
            'classes': self._find_classes(code, language),
            'imports': self._find_imports(code, language),
            'comments': self._find_comments(code, language)
        }
    
    def _find_functions(self, code: str, language: str) -> List[Dict]:
        functions = []
        patterns = {
            'python': r'^\s*def\s+(\w+)\s*\(',
            'java': r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:void|\w+)\s+(\w+)\s*\(',
            'javascript': r'^\s*(?:function|async function)\s+(\w+)\s*\(|^\s*const\s+(\w+)\s*=\s*\(.*\)\s*=>',
            'cpp': r'^\s*(?:void|\w+)\s+(\w+)\s*\(',
            'go': r'^\s*func\s+(\w+)\s*\(',
            'rust': r'^\s*fn\s+(\w+)\s*\('
        }
        
        pattern = patterns.get(language, r'^\s*def\s+(\w+)\s*\(')
        for i, line in enumerate(code.split('\n')):
            match = re.search(pattern, line)
            if match:
                name = match.group(1)
                functions.append({
                    'name': name or 'unknown',
                    'line': i + 1
                })
        return functions
    
    def _find_classes(self, code: str, language: str) -> List[Dict]:
        classes = []
        patterns = {
            'python': r'^\s*class\s+(\w+)',
            'java': r'^\s*(?:public|private)?\s*(?:class|interface)\s+(\w+)',
            'javascript': r'^\s*class\s+(\w+)',
            'cpp': r'^\s*(?:class|struct)\s+(\w+)',
            'go': r'^\s*type\s+(\w+)\s+(?:struct|interface)',
            'rust': r'^\s*(?:struct|enum)\s+(\w+)'
        }
        
        pattern = patterns.get(language, r'^\s*class\s+(\w+)')
        for i, line in enumerate(code.split('\n')):
            match = re.search(pattern, line)
            if match:
                classes.append({
                    'name': match.group(1),
                    'line': i + 1
                })
        return classes
    
    def _find_imports(self, code: str, language: str) -> List[Dict]:
        imports = []
        patterns = {
            'python': r'^\s*(?:import|from)\s+(\w+)',
            'java': r'^\s*import\s+([\w.]+)',
            'javascript': r'^\s*(?:import|require\()\s*["\']([^"\']+)',
            'cpp': r'^\s*#include\s*[<"]([^>"]+)',
            'go': r'^\s*import\s+["\']([^"\']+)',
            'rust': r'^\s*use\s+([\w:]+)'
        }
        
        pattern = patterns.get(language, r'^\s*import\s+(\w+)')
        for i, line in enumerate(code.split('\n')):
            match = re.search(pattern, line)
            if match:
                imports.append({
                    'name': match.group(1),
                    'line': i + 1
                })
        return imports
    
    def _find_comments(self, code: str, language: str) -> List[Dict]:
        comments = []
        markers = {
            'python': ['#'],
            'java': ['//', '/*'],
            'javascript': ['//', '/*'],
            'cpp': ['//', '/*'],
            'go': ['//'],
            'rust': ['//', '/*']
        }
        
        markers_list = markers.get(language, ['#'])
        for i, line in enumerate(code.split('\n')):
            stripped = line.strip()
            for marker in markers_list:
                if stripped.startswith(marker):
                    comments.append({
                        'text': stripped,
                        'line': i + 1
                    })
                    break
        return comments