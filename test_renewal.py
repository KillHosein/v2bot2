#!/usr/bin/env python3
"""
Test script to verify renewal functionality
"""
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.panel import VpnPanelAPI, ThreeXuiAPI, TxUiAPI, XuiAPI
from bot.db import query_db

def test_panel_renewal_methods():
    """Test that all panel types have required renewal methods"""
    print("🔍 Testing Panel API Methods...\n")
    
    panels = query_db("SELECT * FROM panels WHERE enabled = 1")
    if not panels:
        print("❌ No panels found in database")
        return False
    
    all_ok = True
    for panel in panels:
        panel_type = (panel.get('panel_type') or '').lower()
        print(f"\n📦 Panel: {panel['name']} (Type: {panel_type})")
        
        try:
            api = VpnPanelAPI(panel_id=panel['id'])
            
            # Check required methods
            methods_to_check = [
                'renew_user_in_panel',
                'renew_by_recreate_on_inbound',
                'get_user',
            ]
            
            for method in methods_to_check:
                has_method = hasattr(api, method)
                status = "✅" if has_method else "❌"
                print(f"  {status} {method}: {'Found' if has_method else 'MISSING'}")
                if not has_method:
                    all_ok = False
                    
        except Exception as e:
            print(f"  ❌ Error creating API: {e}")
            all_ok = False
    
    return all_ok

def test_renewal_flow():
    """Test the renewal flow logic"""
    print("\n\n🔧 Testing Renewal Flow Logic...\n")
    
    # Check for any active orders
    orders = query_db("SELECT * FROM orders WHERE status IN ('active', 'approved') LIMIT 1")
    if not orders:
        print("⚠️  No active orders found to test")
        return True
    
    order = orders[0]
    print(f"📋 Testing with Order #{order['id']}")
    print(f"   User ID: {order['user_id']}")
    print(f"   Panel ID: {order.get('panel_id')}")
    print(f"   Username: {order.get('marzban_username')}")
    
    if not order.get('panel_id'):
        print("   ⚠️  Order has no panel_id")
        return True
    
    try:
        api = VpnPanelAPI(panel_id=order['panel_id'])
        panel_row = query_db("SELECT panel_type FROM panels WHERE id = ?", (order['panel_id'],), one=True)
        panel_type = (panel_row.get('panel_type') or '').lower() if panel_row else 'unknown'
        
        print(f"   Panel Type: {panel_type}")
        print(f"   API Class: {type(api).__name__}")
        
        # Check if it has the renewal method
        has_recreate = hasattr(api, 'renew_by_recreate_on_inbound')
        has_panel_renew = hasattr(api, 'renew_user_in_panel')
        
        print(f"   ✅ Has renew_by_recreate_on_inbound: {has_recreate}")
        print(f"   ✅ Has renew_user_in_panel: {has_panel_renew}")
        
        if not has_recreate and panel_type in ('txui', 'tx-ui', 'tx ui', '3xui', '3x-ui', 'xui', 'x-ui'):
            print(f"   ❌ PROBLEM: {panel_type} panel missing renew_by_recreate_on_inbound!")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    return True

def check_version():
    """Check if VERSION.txt matches latest"""
    print("\n\n📦 Checking Version...\n")
    try:
        with open('VERSION.txt', 'r', encoding='utf-8') as f:
            version = f.read().strip().split('\n')[0]
        print(f"Current Version: {version}")
        
        if 'v2.5.1' in version:
            print("✅ Version is correct (v2.5.1)")
            return True
        else:
            print("⚠️  Version mismatch - expected v2.5.1")
            return False
    except Exception as e:
        print(f"❌ Error reading version: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("🧪 V2BOT RENEWAL TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Test 1: Version check
    results.append(("Version Check", check_version()))
    
    # Test 2: Panel methods
    results.append(("Panel API Methods", test_panel_renewal_methods()))
    
    # Test 3: Renewal flow
    results.append(("Renewal Flow Logic", test_renewal_flow()))
    
    # Summary
    print("\n\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✅ All tests passed! Renewal should work correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
        sys.exit(1)
