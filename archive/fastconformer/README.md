# FastConformer Archive

This directory contains documentation and test files related to a previous FastConformer streaming implementation.

**Note**: The JARVIS project has since migrated to **NVIDIA Canary-1B Flash** which uses a different architecture (AED - Attention Encoder-Decoder) instead of FastConformer's cache-aware streaming.

## Archived Files

- `FASTCONFORMER_STREAMING.md` - FastConformer streaming implementation guide
- `STREAMING_IMPLEMENTATION_COMPLETE.md` - Completion documentation
- `IMPLEMENTATION_TESTED.md` - Test results
- `SUMMARY_ALL_FIXES.md` - Fix summaries (some general info still relevant)
- `FILTER_FIX.md` - Filter improvements (general concepts still relevant)
- `test_streaming*.py` - FastConformer-specific test scripts

## Current Model

JARVIS now uses:
- **Model**: `nvidia/canary-1b-flash`
- **Architecture**: AED (Attention Encoder-Decoder)
- **Performance**: 1000+ RTFx
- **Documentation**: See `/source-code/docs/NEMO_SETUP.md`

These files are kept for historical reference only.
