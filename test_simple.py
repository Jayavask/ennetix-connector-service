#!/usr/bin/env python3
"""Simple test to check if we can at least parse the Python files"""
import ast
import sys
from pathlib import Path

def test_syntax(file_path):
    """Test if a Python file has valid syntax"""
    try:
        with open(file_path, 'r') as f:
            code = f.read()
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

def main():
    """Test all Python files for syntax errors"""
    project_root = Path(__file__).parent
    app_dir = project_root / "app"
    
    if not app_dir.exists():
        print("❌ app/ directory not found!")
        return 1
    
    print("Testing Python file syntax...")
    print("=" * 60)
    
    python_files = list(app_dir.rglob("*.py"))
    
    if not python_files:
        print("❌ No Python files found in app/")
        return 1
    
    errors = []
    for py_file in sorted(python_files):
        rel_path = py_file.relative_to(project_root)
        is_valid, error = test_syntax(py_file)
        
        if is_valid:
            print(f"✅ {rel_path}")
        else:
            print(f"❌ {rel_path}: {error}")
            errors.append((rel_path, error))
    
    print("=" * 60)
    
    if errors:
        print(f"\n❌ Found {len(errors)} syntax error(s)")
        return 1
    else:
        print(f"\n✅ All {len(python_files)} Python files have valid syntax!")
        print("\nNext: Install dependencies with 'pip install -r requirements.txt'")
        return 0

if __name__ == "__main__":
    sys.exit(main())
