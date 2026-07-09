import re
import ast
from typing import Dict, List, Any

class CodeReviewer:
    def __init__(self):
        # Security patterns
        self.security_patterns = {
            'hardcoded_creds': r'(password|secret|token|api_key)\s*=\s*["\'][^"\']+["\']',
            'sql_injection': r'SELECT.*\+|INSERT.*\+|UPDATE.*\+|DELETE.*\+|f".*SELECT|format\(.*SELECT',
            'command_injection': r'os\.system|subprocess\.call|subprocess\.Popen|eval\(|exec\(',
            'weak_crypto': r'md5|sha1|DES',
            'pickle': r'pickle\.load|pickle\.dump'
        }
    
    def find_bugs(self, code: str, language: str) -> List[Dict]:
        """Find logical bugs"""
        bugs = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines):
            ln = i + 1
            stripped = line.strip()
            
            if stripped.startswith('#'):
                continue
            
            # Division by zero
            if '/' in line and '0' in line and 'def' not in line:
                if line.split('/')[-1].strip() in ['0', 'count']:
                    bugs.append({
                        'line': ln,
                        'type': 'Division by Zero',
                        'description': 'Potential division by zero',
                        'severity': 'critical',
                        'suggested_fix': 'Check if denominator is zero before division'
                    })
            
            # Infinite loop
            if 'while True' in line or 'while 1' in line:
                has_break = any('break' in lines[j] for j in range(i+1, min(i+30, len(lines))))
                if not has_break:
                    bugs.append({
                        'line': ln,
                        'type': 'Infinite Loop',
                        'description': 'Potential infinite loop (no break found)',
                        'severity': 'high',
                        'suggested_fix': 'Add a break condition or limit iterations'
                    })
        
        return bugs
    
    def find_security_issues(self, code: str, language: str) -> List[Dict]:
        """Find security vulnerabilities"""
        issues = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines):
            ln = i + 1
            stripped = line.strip()
            
            if stripped.startswith('#'):
                continue
            
            # Check each security pattern
            for pattern_name, pattern in self.security_patterns.items():
                if re.search(pattern, line, re.IGNORECASE):
                    severity = 'critical' if pattern_name in ['sql_injection', 'command_injection'] else 'high'
                    issues.append({
                        'line': ln,
                        'type': pattern_name.replace('_', ' ').title(),
                        'description': self._get_security_description(pattern_name),
                        'severity': severity,
                        'remediation': self._get_security_remediation(pattern_name)
                    })
                    break  # Only add one issue per line
        
        return issues
    
    def find_performance_issues(self, code: str, language: str) -> List[Dict]:
        """Find performance issues"""
        issues = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines):
            ln = i + 1
            stripped = line.strip()
            
            if stripped.startswith('#'):
                continue
            
            # Nested loops
            if 'for' in line and i < len(lines) - 5:
                nested = sum(1 for j in range(i+1, min(i+15, len(lines))) if 'for' in lines[j])
                if nested >= 2:
                    issues.append({
                        'line': ln,
                        'type': 'Nested Loops',
                        'description': f'Deeply nested loops ({nested+1} levels)',
                        'severity': 'medium',
                        'impact': 'high'
                    })
            
            # Inefficient loop
            if 'range(len(' in line:
                issues.append({
                    'line': ln,
                    'type': 'Inefficient Loop',
                    'description': 'Using range(len()) - consider using enumerate()',
                    'severity': 'low',
                    'impact': 'low'
                })
        
        return issues
    
    def find_style_issues(self, code: str, language: str) -> List[Dict]:
        """Find style issues"""
        issues = []
        lines = code.split('\n')
        found = set()
        
        for i, line in enumerate(lines):
            ln = i + 1
            stripped = line.strip()
            
            if not stripped:
                continue
            
            # Line length
            if len(line) > 100 and not stripped.startswith('#'):
                key = f"Line Length_{ln}"
                if key not in found:
                    found.add(key)
                    issues.append({
                        'line': ln,
                        'type': 'Line Length',
                        'description': f'Line is {len(line)} characters (max 100)',
                        'severity': 'low',
                        'suggestion': 'Break line into multiple lines'
                    })
            
            # Magic numbers
            if not stripped.startswith('#') and '"' not in line and "'" not in line:
                nums = re.findall(r'(?<![a-zA-Z0-9_])\b\d{2,}\b(?![a-zA-Z0-9_])', line)
                for num in nums:
                    num_int = int(num)
                    if num_int > 10 and num_int not in [100, 200, 300, 400, 500]:
                        key = f"Magic Number_{ln}"
                        if key not in found:
                            found.add(key)
                            issues.append({
                                'line': ln,
                                'type': 'Magic Number',
                                'description': f'Magic number {num} found',
                                'severity': 'low',
                                'suggestion': f'Define {num} as a named constant'
                            })
                            break
            
            # Missing docstring
            if stripped.endswith(':') and i < len(lines) - 1:
                if not lines[i+1].strip().startswith(('"""', "'''")):
                    if 'def ' in stripped or 'class ' in stripped:
                        key = f"Missing Documentation_{ln}"
                        if key not in found:
                            found.add(key)
                            issues.append({
                                'line': ln,
                                'type': 'Missing Documentation',
                                'description': 'Missing docstring',
                                'severity': 'medium',
                                'suggestion': 'Add docstring describing purpose'
                            })
        
        return issues
    
    def _get_security_description(self, pattern_name: str) -> str:
        descriptions = {
            'hardcoded_creds': 'Hardcoded credentials found - use environment variables',
            'sql_injection': 'Potential SQL Injection vulnerability - use parameterized queries',
            'command_injection': 'Potential Command Injection - avoid user input in system calls',
            'weak_crypto': 'Weak cryptographic algorithm - use stronger alternatives',
            'pickle': 'Insecure deserialization - avoid pickle for untrusted data'
        }
        return descriptions.get(pattern_name, 'Security issue detected')
    
    def _get_security_remediation(self, pattern_name: str) -> str:
        remediations = {
            'hardcoded_creds': 'Use environment variables or secret management',
            'sql_injection': 'Use parameterized queries (e.g., cursor.execute("SELECT * FROM users WHERE id=?", (user_id,)))',
            'command_injection': 'Use subprocess with list arguments instead of shell=True',
            'weak_crypto': 'Use bcrypt, argon2, or PBKDF2 instead of MD5/SHA1',
            'pickle': 'Use JSON or other safe serialization formats'
        }
        return remediations.get(pattern_name, 'Follow security best practices')