#!/usr/bin/env python3
"""
Initialize Project Script
Cross-platform script to install Python dependencies and frontend dependencies
Works on Windows, Linux, and Mac
"""

import subprocess
import sys
import os
from pathlib import Path

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 50)
    print(text)
    print("=" * 50 + "\n")

def print_success(text):
    """Print success message"""
    print(f"✓ {text}")

def print_error(text):
    """Print error message"""
    print(f"✗ {text}")

def print_info(text):
    """Print info message"""
    print(f"  {text}")

def check_command(command, name, version_flag="--version", use_shell=False):
    """Check if a command is available"""
    try:
        # On Windows, use shell=True for better PATH resolution
        if os.name == 'nt' or use_shell:
            shell = True
            cmd = f"{command} {version_flag}"
        else:
            shell = False
            cmd = [command, version_flag]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            shell=shell
        )
        version = result.stdout.strip() or result.stderr.strip()
        print_success(f"Found {name}: {version}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Try alternative version flag for npm
        if name == "npm" and version_flag == "--version":
            try:
                result = subprocess.run(
                    f"{command} -v" if (os.name == 'nt' or use_shell) else [command, "-v"],
                    capture_output=True,
                    text=True,
                    check=True,
                    shell=(os.name == 'nt' or use_shell)
                )
                version = result.stdout.strip() or result.stderr.strip()
                print_success(f"Found {name}: {version}")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        print_error(f"{name} is not installed or not in PATH")
        return False

def run_command(command, cwd=None, description=""):
    """Run a command and return success status"""
    if description:
        print_info(f"{description}...")
    
    try:
        # Use shell=True on Windows for better compatibility
        shell = os.name == 'nt'
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=shell,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        return False
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def main():
    """Main initialization function"""
    print_header("Initializing Scrutinise Project")
    
    # Check prerequisites
    print("Checking prerequisites...")
    print()
    
    # Check Python
    python_cmd = "python3" if sys.platform != "win32" else "python"
    if not check_command(python_cmd, "Python"):
        print_info("Please install Python 3.8+ and try again")
        sys.exit(1)
    
    # Check pip
    pip_cmd = "pip3" if sys.platform != "win32" else "pip"
    if not check_command(pip_cmd, "pip"):
        print_info("Please install pip and try again")
        sys.exit(1)
    
    # Check Node.js
    if not check_command("node", "Node.js"):
        print_info("Please install Node.js 18+ and try again")
        sys.exit(1)
    
    # Check npm (use shell on Windows for better PATH resolution)
    if not check_command("npm", "npm", use_shell=(os.name == 'nt')):
        print_info("Please install npm and try again")
        sys.exit(1)
    
    # Install Python dependencies
    print_header("Installing Python Dependencies")
    
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print_error("requirements.txt not found")
        sys.exit(1)
    
    # Try installing with --user flag first (for permission issues on Windows)
    pip_install_cmd = [pip_cmd, "install", "--user", "-r", "requirements.txt"]
    if not run_command(pip_install_cmd, description="Installing packages from requirements.txt (with --user flag)"):
        # If --user fails, try without it (might need admin/sudo)
        print_info("Retrying without --user flag...")
        pip_install_cmd = [pip_cmd, "install", "-r", "requirements.txt"]
        if not run_command(pip_install_cmd, description="Installing packages from requirements.txt"):
            print_error("Failed to install Python dependencies")
            print_info("If you see permission errors, try:")
            print_info("  - Running as administrator (Windows) or with sudo (Linux/Mac)")
            print_info("  - Or use: pip install --user -r requirements.txt")
            sys.exit(1)
    
    print_success("Python dependencies installed successfully")
    
    # Install frontend dependencies
    print_header("Installing Frontend Dependencies")
    
    frontend_dir = Path("frontend")
    if not frontend_dir.exists() or not frontend_dir.is_dir():
        print_error("frontend directory not found")
        sys.exit(1)
    
    npm_install_cmd = ["npm", "install"]
    if not run_command(npm_install_cmd, cwd=str(frontend_dir), description="Installing npm packages"):
        print_error("Failed to install frontend dependencies")
        sys.exit(1)
    
    print_success("Frontend dependencies installed successfully")
    
    # Success message
    print_header("Initialization Complete!")
    
    print("Next steps:")
    print_info("1. Set up your .env files with required API keys and configuration")
    print_info("2. Start the Flask backend: cd 'Due Diligence' && python app.py")
    print_info("3. Start the AI SME backend: cd 'AI SME' && uvicorn app:app --reload")
    print_info("4. Start the frontend: cd frontend && npm run dev")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInitialization cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        sys.exit(1)

