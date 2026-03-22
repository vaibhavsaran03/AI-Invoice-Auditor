import os
import json
import yaml
import requests
from litellm import completion

def load_rules():
    """Reads the rules.yaml file into Python."""
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'rules.yaml'))
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def get_vendor_id_with_ai(vendor_name):
    """Uses Groq to semantically match the extracted name to the real ERP ID."""
    vendors_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'erp_mock_data', 'vendors.json'))
    with open(vendors_path, 'r', encoding='utf-8') as file:
        vendors = json.load(file)
    
    prompt = f"Match this invoice vendor name: '{vendor_name}' to the correct vendor_id from this database: {json.dumps(vendors)}. Reply ONLY with the exact vendor_id (e.g., VEND-001) and nothing else."
    
    try:
        response = completion(
            model="groq/llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ AI Semantic Match Error: {e}")
        return ""

def validate_business_rules(structured_data: dict) -> list:
    """Checks the extracted invoice data (including line items) against the Mock ERP."""
    print("🏢 Business Validation Agent: Checking against Mock ERP...")
    rules = load_rules()
    errors = []
    
    # 🌟 GUARD 1: Capture the name and check if it exists at all
    original_name = structured_data.get("vendor_id") # Use .get() without fallback to check for None
    
    if not original_name:
        print("   --> ❌ CRITICAL ERROR: No Vendor ID or Name found in extracted data.")
        errors.append("Critical Error: AI failed to extract any Vendor identification from the document.")
        return errors # EXIT EARLY: Do not continue if we don't know who the vendor is

    vendor_id = original_name
    
    # Resolve the Vendor ID if Groq extracted the name instead
    if not str(vendor_id).startswith("VEND-"):
        print(f"   --> 🧠 Attempting AI Semantic Match for: {vendor_id}")
        vendor_id = get_vendor_id_with_ai(vendor_id)
        
        # 🌟 GUARD 2: Check if AI successfully resolved the name to an ID
        if not vendor_id:
            print("   --> ❌ ERROR: AI could not match vendor name to an ERP ID.")
            errors.append(f"Vendor resolution failed: '{original_name}' does not exist in ERP records.")
            return errors # EXIT EARLY: Cannot check POs or Currencies without a valid ID

        structured_data["vendor_id"] = vendor_id
        structured_data["vendor_name"] = original_name 
    else:
        structured_data["vendor_name"] = original_name

    # ---------------------------------------------------------
    # 1. Check Vendor ERP Database (Currency Check)
    # ---------------------------------------------------------
    try:
        vendors_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'erp_mock_data', 'vendors.json'))
        
        with open(vendors_path, 'r', encoding='utf-8') as file:
            vendors_db = json.load(file)
            
        vendor_data = next((v for v in vendors_db if v.get("vendor_id") == vendor_id), None)
        
        if vendor_data:
            invoice_currency = structured_data.get("currency", "")
            symbol_map = rules.get("currency_symbol_map", {})
            
            if invoice_currency in symbol_map:
                invoice_currency = symbol_map[invoice_currency]
                
            if invoice_currency != vendor_data["currency"]:
                errors.append(f"Currency mismatch! Invoice: {invoice_currency}, ERP: {vendor_data['currency']}")
        else:
            # This handles cases where the resolution returned an ID that isn't actually in the JSON
            errors.append(f"Vendor ID {vendor_id} not found in ERP records.")
            return errors # Exit here because PO check will also fail
            
    except Exception as e:
        print(f"❌ ERP Local Access Error: {e}")
        errors.append("Could not access ERP data.")

    # ---------------------------------------------------------
    # 2. Check Purchase Order Line Items (2-Way Math Matching)
    # ---------------------------------------------------------
    print("   --> 📦 Verifying Line Items against PO Records...")
    try:
        # Search the local Mock ERP files to find the active PO for this vendor
        po_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'erp_mock_data', 'PO Records.json'))
        with open(po_path, 'r', encoding='utf-8') as file:
            all_pos = json.load(file)
            
        # Find the specific PO belonging to our vendor
        vendor_po = next((po for po in all_pos if po.get("vendor_id") == vendor_id), None)
        
        if vendor_po:
            print(f"   --> ✅ Found matching Purchase Order in ERP: {vendor_po['po_number']}")
            
            # Map the ERP items by their SKU code for easy checking
            erp_items = {item["item_code"]: item for item in vendor_po["line_items"]}
            invoice_items = structured_data.get("line_items", [])
            
            # Load tolerances directly from your rules.yaml!
            price_tol = rules.get("tolerances", {}).get("price_difference_percent", 5) / 100.0
            qty_tol = rules.get("tolerances", {}).get("quantity_difference_percent", 0) / 100.0
            
            for inv_item in invoice_items:
                code = inv_item.get("item_code")
                if code not in erp_items:
                    errors.append(f"Item {code} is on the invoice but NOT in the ERP Purchase Order.")
                    continue
                
                erp_item = erp_items[code]
                
                # Verify Quantity (Strict 0% tolerance)
                inv_qty = float(inv_item.get("qty", 0))
                erp_qty = float(erp_item.get("qty", 0))
                if abs(inv_qty - erp_qty) > (erp_qty * qty_tol):
                    errors.append(f"Quantity mismatch for {code}. Invoice: {inv_qty}, ERP: {erp_qty}")
                
                # Verify Unit Price (5% tolerance)
                inv_price = float(inv_item.get("unit_price", 0))
                erp_price = float(erp_item.get("unit_price", 0))
                if abs(inv_price - erp_price) > (erp_price * price_tol):
                    errors.append(f"Price mismatch for {code}. Invoice: {inv_price}, ERP: {erp_price}")
                    
        else:
            errors.append(f"No active Purchase Order found in ERP for vendor {vendor_id}.")
            
    except Exception as e:
        print(f"❌ PO Validation Error: {e}")
        errors.append("Failed to validate line items against ERP.")

    if errors:
        print(f"   --> ⚠️ Business Rule Violations: {errors}")
    else:
        print("   --> 🎉 2-Way Match Passed! All line items, quantities, and prices align perfectly with the ERP tolerances.")
        
    return errors