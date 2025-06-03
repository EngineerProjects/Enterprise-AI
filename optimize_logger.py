#!/usr/bin/env python3
"""
Script to optimize logger calls in Enterprise AI project for performance.
Replaces f-string logger calls with % formatting for better performance.
"""

import re
import os
import sys
from pathlib import Path

def optimize_logger_calls(file_path):
    """
    Optimize logger calls in a file by replacing f-strings with % formatting.
    """
    print(f"Optimizing logger calls in: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern to match logger calls with f-strings
    # Matches: logger.debug(f"text {var} more text")
    pattern = r'logger\.(debug|info|warning|error)\(f"([^"]*?)"\)'
    
    def replace_fstring(match):
        level = match.group(1)
        fstring_content = match.group(2)
        
        # Extract variables from {var} patterns
        var_pattern = r'\{([^}]+)\}'
        variables = re.findall(var_pattern, fstring_content)
        
        # Replace {var} with %s
        msg_template = re.sub(var_pattern, '%s', fstring_content)
        
        # Create the optimized logger call
        if variables:
            var_list = ', '.join(variables)
            return f'logger.{level}("{msg_template}", {var_list})'
        else:
            return f'logger.{level}("{msg_template}")'
    
    # Replace all f-string logger calls
    content = re.sub(pattern, replace_fstring, content)
    
    # Count changes
    original_matches = len(re.findall(pattern, original_content))
    remaining_matches = len(re.findall(pattern, content))
    
    if original_matches > remaining_matches:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ Optimized {original_matches - remaining_matches} logger calls")
        return original_matches - remaining_matches
    else:
        print(f"  • No f-string logger calls found")
        return 0

def main():
    # Base directory for Enterprise AI
    base_dir = "/home/amiche/Projects/Enterprise-AI/enterprise_ai"
    
    # Files to optimize (most critical first)
    priority_files = [
        "llm/tool_executor.py",
        "sandbox/core/sandbox.py", 
        "sandbox/executor.py",
        "llm/ollama/ollama.py",
        "tool/research/deep_research.py",
        "tool/browser/browser.py",
        "tool/research/web_search.py"
    ]
    
    total_optimized = 0
    
    for file_rel_path in priority_files:
        file_path = os.path.join(base_dir, file_rel_path)
        if os.path.exists(file_path):
            total_optimized += optimize_logger_calls(file_path)
        else:
            print(f"  ⚠ File not found: {file_path}")
    
    print(f"\n🚀 Total logger calls optimized: {total_optimized}")

if __name__ == "__main__":
    main()
