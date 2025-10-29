"""
CUDA-Python 13.x Compatibility Shim for NeMo

cuda-python 13.x changed its module structure from:
  - Old: from cuda import cuda
  - New: from cuda.bindings import driver

This shim provides backward compatibility for NeMo which expects the old import style.
Import this module before importing NeMo to enable CUDA graph optimization.
"""

def setup_cuda_compatibility():
    """Setup compatibility layer for cuda-python 12.x with NeMo"""
    try:
        # Import the new-style modules directly
        from cuda.bindings import driver as cuda_driver
        from cuda.bindings import runtime as cudart
        from cuda.bindings import nvrtc as nvrtc_mod

        # Create compatibility layer in cuda module namespace
        import cuda

        # Map new bindings to old expected names
        cuda.cuda = cuda_driver
        cuda.cudart = cudart
        cuda.nvrtc = nvrtc_mod

        # Add version without accessing deprecated cuda.__version__
        # Get version directly from package metadata
        import importlib.metadata
        version = importlib.metadata.version('cuda-python')

        # Store in a way that doesn't trigger deprecation warning
        object.__setattr__(cuda, '__version__', version)

        return True
    except ImportError as e:
        # cuda-python not installed or incompatible version
        print(f"Warning: Could not setup CUDA compatibility: {e}")
        return False

# Auto-setup when imported
setup_cuda_compatibility()
