#!/bin/bash
# Install PyTorch 2.6.0 with CUDA support
# This will enable GPU acceleration for your JARVIS system

set -e  # Exit on error

echo "=========================================="
echo "Installing PyTorch 2.6.0 with CUDA 12.4"
echo "=========================================="

cd /home/paul/Work/jarvis/source-code

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "ERROR: venv not found at $(pwd)/venv"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

echo ""
echo "Current PyTorch version:"
python -c "import torch; print(f'PyTorch: {torch.__version__}')" || echo "PyTorch not installed"

echo ""
echo "Step 1: Uninstalling CPU-only PyTorch..."
pip uninstall -y torch torchaudio torchvision 2>/dev/null || true

echo ""
echo "Step 2: Installing PyTorch 2.6.0 with CUDA 12.4..."
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124

echo ""
echo "Step 3: Verifying GPU support..."
python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'GPU count: {torch.cuda.device_count()}')
    print(f'GPU name: {torch.cuda.get_device_name(0)}')
    print('')
    print('✓ GPU support ENABLED!')
else:
    print('')
    print('✗ ERROR: GPU support not available')
    exit(1)
"

echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run: python test_hungarian_transcription.py"
echo "2. Expected: ~500x RTFx (vs current 1x)"
echo "3. GPU should show in logs: 'loaded on GPU: NVIDIA GeForce RTX 3080'"
echo ""
