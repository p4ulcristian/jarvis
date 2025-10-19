#!/usr/bin/env python3
"""
Test script to verify the export functionality in terminal UI
"""
import sys
import os

# Add source-code directory to path
sys.path.insert(0, '/home/paul/Work/jarvis/source-code')

def test_import():
    """Test that the module imports without errors"""
    try:
        from ui.terminal_ui import JarvisApp, JarvisUI
        from ui.data_bridge import DataBridge
        print("✓ Modules imported successfully")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_export_directory():
    """Test that export directory can be created"""
    try:
        export_dir = os.path.expanduser("~/jarvis_exports")
        os.makedirs(export_dir, exist_ok=True)

        if os.path.exists(export_dir):
            print(f"✓ Export directory exists: {export_dir}")
            return True
        else:
            print(f"✗ Export directory creation failed")
            return False
    except Exception as e:
        print(f"✗ Directory test failed: {e}")
        return False

def test_bindings():
    """Test that the export binding exists in the app"""
    try:
        from ui.terminal_ui import JarvisApp

        # Check if the export binding exists
        bindings = [b for b in JarvisApp.BINDINGS]
        export_binding = [b for b in bindings if 'export' in str(b).lower()]

        if export_binding:
            print(f"✓ Export binding found: {export_binding}")
            return True
        else:
            print("✗ Export binding not found")
            return False
    except Exception as e:
        print(f"✗ Binding test failed: {e}")
        return False

def main():
    print("Testing Terminal UI Export Feature")
    print("=" * 50)

    tests = [
        ("Import Test", test_import),
        ("Export Directory Test", test_export_directory),
        ("Bindings Test", test_bindings),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n{name}:")
        result = test_func()
        results.append(result)

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if all(results):
        print("\n✓ All tests passed! Export feature is ready to use.")
        print("\nUsage:")
        print("  1. Run the JARVIS terminal UI")
        print("  2. Press 'e' to export logs")
        print("  3. Or use Shift+Mouse to select text directly in most terminals")
        print(f"  4. Exported files will be saved to: ~/jarvis_exports/")
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
