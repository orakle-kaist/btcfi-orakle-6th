import os
import sys
import contextlib
import tempfile

@contextlib.contextmanager
def suppress_output():
    """Suppress all stdout/stderr output including C/Rust level"""
    # Save original file descriptors
    old_stdout = os.dup(1)
    old_stderr = os.dup(2)
    
    try:
        # Open devnull
        devnull = os.open(os.devnull, os.O_WRONLY)
        
        # Redirect stdout and stderr to devnull
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        
        # Close devnull fd
        os.close(devnull)
        
        # Also redirect Python's sys.stdout/stderr
        old_python_stdout = sys.stdout
        old_python_stderr = sys.stderr
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
        
        yield
        
    finally:
        # Restore Python's stdout/stderr
        sys.stdout.close()
        sys.stderr.close()
        sys.stdout = old_python_stdout
        sys.stderr = old_python_stderr
        
        # Restore original file descriptors
        os.dup2(old_stdout, 1)
        os.dup2(old_stderr, 2)
        
        # Close the saved descriptors
        os.close(old_stdout)
        os.close(old_stderr)