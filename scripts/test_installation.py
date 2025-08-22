#!/usr/bin/env python3
"""Test script to verify TEXAS installation and imports."""

def test_imports():
    """Test that all main TEXAS modules can be imported."""
    try:
        import TEXAS
        print("✓ TEXAS package imported successfully")
        
        from TEXAS import constants
        print("✓ TEXAS.constants imported")
        
        from TEXAS.models import logistics
        print("✓ TEXAS.models.logistics imported")
        
        from TEXAS.data import builder
        print("✓ TEXAS.data.builder imported")
        
        from TEXAS.plotting import prior_plot
        print("✓ TEXAS.plotting.prior_plot imported")
        
        print("\n✓ All imports successful! Your TEXAS package is working correctly.")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

if __name__ == "__main__":
    test_imports()
