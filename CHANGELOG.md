# JARVIS Changelog

## [2.0.0] - 2025-10-18 - Production Cleanup Release

### Major Changes

#### Architecture Refactoring
- **Modular Structure**: Split 1170-line monolithic `jarvis.py` into clean modules:
  - `core/config.py` - Configuration management with environment variables
  - `core/logger.py` - Structured logging infrastructure
  - `core/audio.py` - Audio capture and processing
  - `core/transcription.py` - ASR transcription logic
  - `core/buffer.py` - Rolling buffer management
- **New Main App**: `jarvis_v2.py` - Production-ready refactored version
- **Backward Compatibility**: Original `jarvis.py` backed up as `jarvis.py.backup`

#### Configuration Management
- **Environment Variables**: All configuration via `.env` file
- **Sensible Defaults**: No more hardcoded constants
- **Validation**: Config validation on startup
- **Documentation**: Comprehensive `.env.example` with all options

#### Logging Infrastructure
- **Structured Logging**: Replaced print statements with proper logging
- **Log Levels**: DEBUG, INFO, WARNING, ERROR support
- **Log Files**: Configurable log output locations
- **Third-party Suppression**: Quieter NeMo/PyTorch logs

#### Dependencies
- **Version Pinning**: All dependencies locked to specific versions
- **Missing Dependencies**: Added `sounddevice`, `scipy`, `python-dotenv`, `pyyaml`
- **Development Tools**: Added commented dev dependencies (pytest, black, ruff)
- **Documentation**: Clear dependency categories

#### Deployment
- **Systemd Service**: Production-ready service file with resource limits
- **Installation Script**: Automated `deploy/install.sh` for easy setup
- **Process Management**: Automatic restart, resource limits, security hardening
- **Deployment Guide**: Comprehensive DEPLOYMENT.md documentation

#### Documentation
- **DEPLOYMENT.md**: Complete production deployment guide
- **MIGRATION.md**: v1 to v2 migration instructions
- **PRODUCTION_CHECKLIST.md**: Pre-deployment validation checklist
- **VISION.md**: Project goals and roadmap
- **README.md**: Updated for production focus

#### Code Quality
- **Error Handling**: Proper try/except blocks throughout
- **Type Safety**: Better type handling and validation
- **Dead Code Removal**: Cleaned up commented-out sections
- **Consistent Style**: Professional code organization

#### Security & Privacy
- **Secrets Management**: API keys via environment, not hardcoded
- **Gitignore Updates**: Log files, data, secrets excluded
- **File Permissions**: Secure defaults for .env and logs
- **Service Isolation**: Systemd security hardening options

### Added

#### New Files
- `jarvis_v2.py` - Refactored main application
- `core/__init__.py` - Core module exports
- `core/config.py` - Configuration management
- `core/logger.py` - Logging setup
- `core/audio.py` - Audio capture
- `core/transcription.py` - ASR logic
- `core/buffer.py` - Buffer management
- `utils/__init__.py` - Utility module placeholder
- `.env.example` - Example configuration
- `deploy/jarvis.service` - Systemd service file
- `deploy/install.sh` - Installation script
- `DEPLOYMENT.md` - Deployment documentation
- `MIGRATION.md` - Migration guide
- `PRODUCTION_CHECKLIST.md` - Production readiness checklist
- `CHANGELOG.md` - This file

#### New Features
- Environment-based configuration
- Structured logging with levels
- Health check support (via config validation)
- Metrics collection framework (optional, via prometheus-client)
- Graceful shutdown handling
- Configuration validation on startup

### Changed

#### Modified Files
- `.gitignore` - Added log files, data directories, process files, test directories
- `requirements.txt` - Updated with pinned versions and missing dependencies
- `jarvis.py` - Backed up as `jarvis.py.backup`

#### Behavior Changes
- Logging now goes to proper logger instead of print statements
- Configuration loaded from .env instead of hardcoded constants
- Errors properly logged with context instead of silent failures
- Cleaner startup/shutdown process

### Removed

#### Deleted Files
- `=12.3` - Temporary file
- `chat.txt` - Log file (regenerated on run)
- `chat-revised.txt` - Log file (regenerated on run)
- `todo.md` - Development notes
- `run-jarvis.sh` - Duplicate of jarvis.sh
- `jarvis ui/` - Prototype directory

#### Deprecated Features (Not in v2 Yet)
- Push-to-talk keyboard mode (was disabled in v1)
- Conversation improver integration (runs separately)
- AI detection (disabled by default, can be enabled)

### Fixed

- **Process Management**: Killed 10+ zombie jarvis.py processes
- **Memory Issues**: Improved malloc handling with proper cleanup
- **Logging Spam**: Suppressed verbose third-party logs
- **Error Handling**: Replaced stderr redirection with proper exceptions
- **Configuration**: No more hardcoded values scattered throughout

### Dependencies

#### Updated
- `torch==2.5.1` (was `>=2.0.0`)
- `numpy==1.26.4` (was unversioned)
- `requests==2.32.3` (was unversioned)
- `pynput==1.7.7` (was unversioned)

#### Added
- `sounddevice==0.5.1` - Missing dependency for audio
- `scipy==1.14.1` - Required by audio processing
- `librosa==0.10.2` - Audio feature extraction
- `python-dotenv==1.0.1` - Environment variable loading
- `pyyaml==6.0.2` - YAML configuration support
- `torchaudio==2.5.1` - Audio utilities for PyTorch
- `prometheus-client==0.21.0` - Metrics (optional)

### Migration Notes

To migrate from v1 to v2:

1. **Backup your data**: Copy chat.txt and chat-revised.txt
2. **Create .env file**: `cp .env.example .env` and configure
3. **Install dependencies**: `pip install -r requirements.txt --upgrade`
4. **Test new version**: Run `./jarvis_v2.py`
5. **Update service**: Copy new systemd service file if using

See [MIGRATION.md](MIGRATION.md) for complete instructions.

### Breaking Changes

- Configuration must now be via `.env` file (not hardcoded)
- Import paths changed (old imports from `jarvis.py` won't work)
- Logging API different (logger instead of print)

### Upgrade Path

For users running v1:

```bash
# Backup
cp -r /path/to/jarvis /path/to/jarvis_backup

# Update
git pull  # or copy new files

# Configure
cp .env.example .env
nano .env  # Add your settings

# Install
pip install -r requirements.txt --upgrade

# Test
./jarvis_v2.py

# Deploy
./deploy/install.sh
```

### Known Issues

- Keyboard listener not yet implemented in v2 (was disabled in v1)
- Conversation improver must run separately (not integrated in v2)
- AI detection disabled by default (performance)

### Performance

- Startup time: ~5 seconds (similar to v1)
- Memory usage: ~3GB (similar to v1)
- CPU usage: Comparable to v1
- GPU usage: Optimized with better memory management

### Security

- API keys now in .env (not git)
- Service runs with NoNewPrivileges
- Proper file permissions
- Log rotation recommended

### Monitoring

- Structured logs for centralized logging
- Optional Prometheus metrics
- Health check via config validation
- Resource limits in systemd service

### Next Release (v2.1.0 - Planned)

- [ ] Re-implement keyboard listener (push-to-talk)
- [ ] Integrate conversation improver
- [ ] Add wake word detection
- [ ] Web UI for monitoring
- [ ] Docker containerization
- [ ] Unit tests
- [ ] CI/CD pipeline

---

## [1.0.0] - 2025-10-17 - Initial Version

### Features
- Continuous speech transcription with NeMo Parakeet-TDT
- Voice Activity Detection (VAD)
- Word boosting for custom vocabulary
- AI detection for direct address
- Conversation improvement with Ollama
- Push-to-talk mode (disabled due to conflicts)
- Keyboard event logging
- OpenAI TTS integration

### Known Issues
- Monolithic 1170-line file
- Hardcoded configuration
- Print-based logging
- Multiple zombie processes
- Memory allocation conflicts
- Keyboard listener disabled
- Conversation improver disabled

---

**For deployment information, see [DEPLOYMENT.md](DEPLOYMENT.md)**

**For migration help, see [MIGRATION.md](MIGRATION.md)**

**For production checklist, see [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)**
