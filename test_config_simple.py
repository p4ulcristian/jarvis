#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'source-code'))

from core.config import Config

config = Config()
print('✓ Config loaded successfully')
print(f'Model: {config.model_name}')
print(f'Language: {config.canary_source_lang} → {config.canary_target_lang}')
print(f'Task: {config.canary_task}')
print(f'Beam size: {config.canary_beam_size}')
print(f'PnC: {config.canary_pnc}')
