#!/usr/bin/env python3
"""
Start All Services Script
Cross-platform script to start Due Diligence, AI SME, and Frontend services
Works on Windows, Linux, and Mac
"""

import subprocess
import sys
import os
import time
import signal
from pathlib import Path

# Global list to store process references
processes = []

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60 + "\n")

def print_success(text):
    """Print success message"""
    print(f"✓ {text}")

def print_error(text):
    """Print error message"""
    print(f"✗ {text}")

def print_info(text):
    """Print info message"""
    print(f"  {text}")

def cleanup_processes():
    """Terminate all started processes"""
    print("\n\nShutting down services...")
    for process in processes:
        try:
            if process.poll() is None:  # Process is still running
                if os.name == 'nt':  # Windows
                    process.terminate()
                    time.sleep(1)
                    if process.poll() is None:
                        process.kill()
                else:  # Linux/Mac
                    process.send_signal(signal.SIGTERM)
                    time.sleep(1)
                    if process.poll() is None:
                        process.kill()
        except Exception as e:
            print_error(f"Error stopping process: {e}")
    print("All services stopped.")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    cleanup_processes()
    sys.exit(0)

def start_service(name, command, cwd, description="", wait_time=3):
    """Start a service in a subprocess"""
    try:
        print_info(f"Starting {name}...")
        if description:
            print_info(f"  {description}")
        
        # Use shell=True on Windows for better compatibility
        shell = os.name == 'nt'
        
        # On Windows, redirect output to avoid blocking
        # On Unix, we can still capture but won't block
        if os.name == 'nt':
            # Windows: redirect to DEVNULL to avoid blocking
            stdout = subprocess.DEVNULL
            stderr = subprocess.DEVNULL
        else:
            # Unix: can use PIPE but we'll read it asynchronously
            stdout = subprocess.PIPE
            stderr = subprocess.PIPE
        
        # Start the process
        process = subprocess.Popen(
            command,
            cwd=cwd,
            shell=shell,
            stdout=stdout,
            stderr=stderr,
            text=True,
            bufsize=1
        )
        
        processes.append(process)
        
        # Give it a moment to start
        time.sleep(wait_time)
        
        # Check if process is still running
        if process.poll() is None:
            print_success(f"{name} started (PID: {process.pid})")
            return True
        else:
            # Process exited immediately, try to read error
            try:
                stdout, stderr = process.communicate(timeout=1)
                error_msg = stderr if stderr else stdout
            except:
                error_msg = "Process exited immediately"
            
            print_error(f"{name} failed to start")
            if error_msg:
                print_info(f"Error: {error_msg[:300]}")
            return False
            
    except Exception as e:
        print_error(f"Failed to start {name}: {str(e)}")
        return False

def main():
    """Main function to start all services"""
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    # SIGTERM is not available on Windows
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    print_header("Starting Scrutinise Services")
    
    # Get base directory
    base_dir = Path(__file__).parent.resolve()
    
    # Check if required directories exist
    due_diligence_dir = base_dir / "Due Diligence"
    ai_sme_dir = base_dir / "AI SME"
    frontend_dir = base_dir / "frontend"
    
    if not due_diligence_dir.exists():
        print_error("Due Diligence directory not found")
        sys.exit(1)
    
    if not ai_sme_dir.exists():
        print_error("AI SME directory not found")
        sys.exit(1)
    
    if not frontend_dir.exists():
        print_error("frontend directory not found")
        sys.exit(1)
    
    # Determine Python command
    python_cmd = "python3" if sys.platform != "win32" else "python"
    
    # Start Due Diligence (Flask)
    print_header("Starting Due Diligence Service")
    flask_cmd = [python_cmd, "app.py"]
    if not start_service(
        "Due Diligence (Flask)",
        flask_cmd,
        str(due_diligence_dir),
        f"Running: {' '.join(flask_cmd)}",
        wait_time=3
    ):
        cleanup_processes()
        sys.exit(1)
    
    # Start AI SME (FastAPI)
    print_header("Starting AI SME Service")
    uvicorn_cmd = ["uvicorn", "app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
    if not start_service(
        "AI SME (FastAPI)",
        uvicorn_cmd,
        str(ai_sme_dir),
        f"Running: {' '.join(uvicorn_cmd)}",
        wait_time=3
    ):
        cleanup_processes()
        sys.exit(1)
    
    # Start Frontend (give it more time as npm can be slower)
    print_header("Starting Frontend Service")
    npm_cmd = ["npm", "run", "dev"]
    if not start_service(
        "Frontend (React/Vite)",
        npm_cmd,
        str(frontend_dir),
        f"Running: {' '.join(npm_cmd)}",
        wait_time=5
    ):
        cleanup_processes()
        sys.exit(1)
    
    # Success message
    print_header("All Services Started Successfully!")
    
    print("Services running:")
    print_info("  • Due Diligence (Flask): http://localhost:5050")
    print_info("  • AI SME (FastAPI): http://localhost:8000")
    print_info("  • Frontend (React/Vite): http://localhost:5173")
    print()
    print("Note: Service output is hidden. For detailed logs, run services individually:")
    print_info("  • Due Diligence: cd 'Due Diligence' && python app.py")
    print_info("  • AI SME: cd 'AI SME' && uvicorn app:app --reload")
    print_info("  • Frontend: cd frontend && npm run dev")
    print()
    print("Press Ctrl+C to stop all services")
    print()
    
    # Monitor processes and wait
    try:
        while True:
            time.sleep(1)
            # Check if any process has died
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    print_error(f"Service {i+1} has stopped unexpectedly")
                    if stderr:
                        print_info(f"Error output: {stderr[:500]}")
                    cleanup_processes()
                    sys.exit(1)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup_processes()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        cleanup_processes()
        sys.exit(1)

