import yaml
import os
import json
from litellm import completion

def load_rules():
    """Reads the rules.yaml file into Python."""
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'rules.yaml'))
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        print(f" Validation Error: Could not load the rulebook! {e}")
        return None

def extract_structured_data(text: str) -> dict:
    """Uses Groq AI to extract BOTH header data and nested line items."""
    print(" Validation Agent: Asking Groq to extract headers AND line items...")
    
    messages = [
        {
            "role": "system",
            "content": """You are an advanced AI data extraction agent. Extract data from the invoice into a strict JSON format.
            You must include these header fields: invoice_no, invoice_date, vendor_id, currency, total_amount.
            You MUST ALSO extract a list called 'line_items'. Every item in 'line_items' must be an object containing: item_code, description, qty (number), unit_price (number), and total (number).
            Reply ONLY with the raw JSON. Do not include ```json formatting blocks."""
        },
        {
            "role": "user",
            "content": text
        }
    ]
    
    try:
        response = completion(
            model="groq/llama-3.1-8b-instant",
            messages=messages,
            temperature=0.1
        )
        
        raw_output = response.choices[0].message.content
        clean_json = raw_output.replace("```json", "").replace("```", "").strip()
        
        return json.loads(clean_json)
    
    except Exception as e:
        print(f"AI Extraction Error: {e}")
        return {}
    
def validate_invoice(translated_text: str) -> dict:
    """The main runner: extracts data, then checks it against the rules."""
    print("✅ Validation Agent: Starting validation process...")
    rules = load_rules()
    
    # Ask AI to get the structured dictionary
    structured_data = extract_structured_data(translated_text)
    print(f"   --> Extracted Data: {structured_data}")
    
    errors = []
    
    # Check against rules.yaml!
    if rules and "required_fields" in rules:
        required_headers = rules["required_fields"].get("header", [])
        
        for field in required_headers:
            # If the field is missing or empty, flag it!
            if field not in structured_data or not structured_data[field]:
                errors.append(f"Missing required field: {field}")
                
    if errors:
        print(f"   --> Rule Violations Found: {errors}")
    else:
        print("   -->  Success! All required header fields are present.")
        
    # return BOTH the extracted data and the errors
    return {"structured_data": structured_data, "errors": errors}