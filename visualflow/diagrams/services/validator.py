"""
Mermaid Syntax Validator - Validates and aggressively fixes Mermaid code
"""

import re
import logging
from typing import Tuple, Optional, List

logger = logging.getLogger(__name__)


class MermaidValidator:
    """
    Validates and fixes Mermaid syntax errors
    This is the LAST LINE OF DEFENSE before rendering
    """
    
    # Reserved keywords that cannot be used as node IDs
    RESERVED_KEYWORDS = [
        'end', 'start', 'subgraph', 'graph', 'classDef', 
        'class', 'click', 'callback', 'link', 'style'
    ]
    
    # Valid Mermaid diagram types
    VALID_DIAGRAM_TYPES = [
        'graph TD', 'graph LR', 'graph BT', 'graph RL',
        'flowchart TD', 'flowchart LR', 'flowchart BT', 'flowchart RL',
        'sequenceDiagram', 'classDiagram', 'stateDiagram-v2',
        'erDiagram', 'gantt', 'pie', 'journey', 'gitGraph',
        'mindmap', 'timeline', 'quadrantChart'
    ]
    
    def __init__(self):
        """Initialize validator"""
        pass
    
    def validate_and_fix(self, mermaid_code: str, max_attempts: int = 2) -> Tuple[str, bool, Optional[str]]:
        """
        Validate and aggressively fix Mermaid syntax with loop protection
        
        Args:
            mermaid_code: The Mermaid code to validate
            max_attempts: Maximum number of fix attempts (default: 2)
            
        Returns:
            Tuple[str, bool, Optional[str]]: (fixed_code, is_valid, error_message)
        """
        if not mermaid_code or not mermaid_code.strip():
            return "", False, "Empty Mermaid code"
        
        previous_code = None
        
        for attempt in range(max_attempts):
            logger.info(f"🔍 Validation attempt {attempt + 1}/{max_attempts}")
            
            # Check if we're stuck (code not changing)
            if previous_code == mermaid_code:
                logger.warning("⚠️ Code not changing, breaking loop to avoid infinite retry")
                break
            
            previous_code = mermaid_code
            
            # Apply all fixes
            mermaid_code = self._apply_all_fixes(mermaid_code)
            
            # Check for common errors
            errors = self._check_syntax_errors(mermaid_code)
            
            if not errors:
                logger.info("✅ Validation passed!")
                return mermaid_code, True, None
            
            logger.warning(f"⚠️ Found {len(errors)} errors: {errors[:2]}")
            
            # Apply targeted fixes based on errors
            new_code = self._fix_specific_errors(mermaid_code, errors)
            
            # If no changes were made, break to avoid infinite loop
            if new_code == mermaid_code:
                logger.warning("⚠️ Fixes not improving code, breaking early")
                break
            
            mermaid_code = new_code
        
        # Final validation check
        final_errors = self._check_syntax_errors(mermaid_code)
        if final_errors:
            error_msg = f"Validation warnings: {'; '.join(final_errors[:2])}"
            logger.warning(error_msg)
            # Return code anyway - best effort
            return mermaid_code, False, error_msg
        
        return mermaid_code, True, None
    
    def _apply_all_fixes(self, code: str) -> str:
        """Apply all known fixes in sequence"""
        code = self._remove_code_fences(code)
        code = self._fix_mixed_brackets(code)
        code = self._fix_edge_labels(code)
        code = self._sanitize_node_ids(code)
        code = self._fix_reserved_keywords(code)
        code = self._remove_styling(code)
        code = self._fix_whitespace(code)
        return code
    
    def _check_syntax_errors(self, code: str) -> List[str]:
        """Check for common Mermaid syntax errors"""
        errors = []
        lines = code.split('\n')
        
        # Check if diagram type is present
        first_line = lines[0].strip() if lines else ""
        if not any(first_line.startswith(dt) for dt in self.VALID_DIAGRAM_TYPES):
            errors.append("Invalid or missing diagram type declaration")
        
        # Check for mixed brackets (critical error)
        if re.search(r'\[\((?!\s*\))|(?<!\()\s*\)\]|\(\]|\[\)', code):
            errors.append("Mixed bracket syntax detected")
        
        # Check for incomplete edge syntax
        if re.search(r'--\|[^\|]*\|(?!-->|\.\.>|==>|-\.->)', code):
            errors.append("Incomplete edge label syntax")
        
        # Check for emojis or special chars in node IDs
        node_id_pattern = r'\b([^\s\[\(\{]+)[\[\(\{]'
        for match in re.finditer(node_id_pattern, code):
            node_id = match.group(1)
            # Skip if it's an arrow or connector
            if node_id in ['--', '-.-', '==', '-.', '-->']:
                continue
            if re.search(r'[^a-zA-Z0-9_]', node_id):
                errors.append(f"Invalid characters in node ID: {node_id}")
                break  # Only report first occurrence
        
        # Check for reserved keywords as node IDs
        for keyword in self.RESERVED_KEYWORDS:
            if re.search(rf'\b{keyword}[\[\(\{{]', code, re.IGNORECASE):
                errors.append(f"Reserved keyword used as node ID: {keyword}")
                break
        
        return errors
    
    def _remove_code_fences(self, code: str) -> str:
        """Remove markdown code fences"""
        if "```mermaid" in code:
            code = re.sub(r'```mermaid\s*\n', '', code)
            code = re.sub(r'\n?```\s*$', '', code)
        elif "```" in code:
            code = re.sub(r'```\s*\n', '', code)
            code = re.sub(r'\n?```\s*$', '', code)
        return code.strip()
    
    def _fix_mixed_brackets(self, code: str) -> str:
        """Fix mixed bracket syntax - CRITICAL"""
        # Fix [( )] -> [(  )]
        code = re.sub(r'\[\(\s*([^\]]+?)\s*\)\]', r'[(\1)]', code)
        
        # Fix [( xx] -> [xx]
        code = re.sub(r'\[\(\s*([^\]]+?)\s*\]', r'[\1]', code)
        
        # Fix [xx)] -> [xx]
        code = re.sub(r'\[\s*([^\]]+?)\s*\)\]', r'[\1]', code)
        
        # Fix (]xx) -> (xx)
        code = re.sub(r'\(\s*\]([^\)]+?)\)', r'(\1)', code)
        
        # Fix standalone [) or (] 
        code = re.sub(r'\[\)', '[', code)
        code = re.sub(r'\(\]', '(', code)
        
        return code
    
    def _fix_edge_labels(self, code: str) -> str:
        """Fix edge label syntax"""
        # Fix incomplete edge syntax: --|text| -> -->|text|
        code = re.sub(r'--\|([^\|]+)\|(?!-->)', r'-->|\1|', code)
        
        # Fix emoji-only edges: ensure there's an arrow type
        code = re.sub(r'(?<!-)-\|([^\|]+)\|', r'-->|\1|', code)
        
        # Fix edges without proper arrow: A --|text| B -> A -->|text| B
        code = re.sub(r'(\w+)\s+--\|([^\|]+)\|\s+(\w+)', r'\1 -->|\2| \3', code)
        
        return code
    
    def _sanitize_node_ids(self, code: str) -> str:
        """Sanitize node IDs - remove special characters"""
        lines = code.split('\n')
        fixed_lines = []
        node_id_map = {}
        
        for line in lines:
            # Find node definitions: nodeId[label] or nodeId(label), etc.
            def replace_node_id(match):
                full_match = match.group(0)
                node_id = match.group(1)
                bracket_start = match.group(2)
                label = match.group(3)
                bracket_end = match.group(4)
                
                # Skip if it's already clean
                if re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', node_id):
                    return full_match
                
                # Check if we've already mapped this ID
                if node_id in node_id_map:
                    clean_id = node_id_map[node_id]
                else:
                    # Clean the ID
                    clean_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id)
                    
                    # Ensure ID starts with letter
                    if not clean_id or not clean_id[0].isalpha():
                        clean_id = 'node' + clean_id if clean_id else 'node' + str(abs(hash(node_id)) % 10000)
                    
                    # Check if it's a reserved keyword
                    if clean_id.lower() in [kw.lower() for kw in self.RESERVED_KEYWORDS]:
                        clean_id = clean_id + 'Node'
                    
                    node_id_map[node_id] = clean_id
                
                return f"{clean_id}{bracket_start}{label}{bracket_end}"
            
            # Match node definitions with various bracket types
            line = re.sub(
                r'(\S+?)([\[\(\{]|\[\(|\(\(|\[\[)(.*?)([\]\)\}]|\)\]|\)\)|\]\])',
                replace_node_id,
                line
            )
            
            # Also fix node IDs in connections (without brackets)
            # A --> B style connections
            for old_id, new_id in node_id_map.items():
                # Only replace whole word matches
                line = re.sub(rf'\b{re.escape(old_id)}\b(?![\[\(\{{])', new_id, line)
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_reserved_keywords(self, code: str) -> str:
        """Fix reserved keywords used as node IDs"""
        for keyword in self.RESERVED_KEYWORDS:
            # Fix in node definitions: keyword[label] -> keywordNode[label]
            code = re.sub(
                rf'\b{keyword}(?=[\[\(\{{])',
                f'{keyword}Node',
                code,
                flags=re.IGNORECASE
            )
            
            # Fix in connections
            code = re.sub(
                rf'(-->|---|\.\.>|==>|-\.->)\s+{keyword}\b',
                rf'\1 {keyword}Node',
                code,
                flags=re.IGNORECASE
            )
            
            code = re.sub(
                rf'\b{keyword}\s+(-->|---|\.\.>|==>|-\.->)',
                rf'{keyword}Node \1',
                code,
                flags=re.IGNORECASE
            )
        
        return code
    
    def _remove_styling(self, code: str) -> str:
        """Remove unsupported styling directives"""
        lines = code.split('\n')
        clean_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Remove classDef lines
            if stripped.startswith('classDef '):
                continue
            
            # Remove class styling (but keep classDiagram)
            if stripped.startswith('class ') and '{' not in line and '--' not in line:
                continue
            
            # Remove style lines
            if stripped.startswith('style '):
                continue
            
            clean_lines.append(line)
        
        return '\n'.join(clean_lines)
    
    def _fix_whitespace(self, code: str) -> str:
        """Fix excessive whitespace"""
        # Remove multiple blank lines
        code = re.sub(r'\n\s*\n\s*\n', '\n\n', code)
        
        # Remove trailing whitespace
        lines = [line.rstrip() for line in code.split('\n')]
        
        # Remove leading/trailing blank lines
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        return '\n'.join(lines)
    
    def _fix_specific_errors(self, code: str, errors: List[str]) -> str:
        """Apply targeted fixes based on specific errors"""
        for error in errors:
            if "Mixed bracket" in error:
                code = self._fix_mixed_brackets(code)
            
            elif "Incomplete edge" in error:
                code = self._fix_edge_labels(code)
            
            elif "Invalid characters in node ID" in error:
                code = self._sanitize_node_ids(code)
            
            elif "Reserved keyword" in error:
                code = self._fix_reserved_keywords(code)
        
        return code


# Create singleton instance
validator = MermaidValidator()
