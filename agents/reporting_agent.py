import os
import json
import yaml
from litellm import completion

def load_rules():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'rules.yaml'))
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def generate_report(structured_data: dict, data_errors: list, erp_errors: list, confidence: float) -> dict:
    """Generates a final summary and saves the reports to the output folder."""
    print("📊 Reporting Agent: Generating final audit report...")
    rules = load_rules()
    
    all_errors = data_errors + erp_errors
    
    # 1. Make a Recommendation
    if len(all_errors) == 0:
        recommendation = "Approve"
    else:
        recommendation = "Manual Review"
        
    # 2. Ask Groq to summarize the issues
    display_name = structured_data.get("vendor_name", structured_data.get("vendor_id", "Unknown Vendor"))
    
    summary_text = f"No discrepancies found for {display_name}. Invoice data matches ERP records."
    if all_errors:
        print("   --> 🧠 Asking Groq to summarize the discrepancies...")
        prompt = f"Summarize these invoice discrepancies for a human auditor: {all_errors}. Keep it to two sentences."
        try:
            response = completion(
                model="groq/llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            summary_text = response.choices[0].message.content.strip()
        except Exception as e:
            summary_text = f"Errors found: {all_errors}"

    # 3. Build the final report
    final_report = {
        "invoice_details": {
            **structured_data, 
            "confidence": confidence  # <--- This is what the Sidebar needs!
        },
        "discrepancy_summary": summary_text, # Assuming you have this variable
        "recommendation": recommendation
    }

    # 4. Save to files (JSON and HTML)
    output_dir = rules.get("reporting", {}).get("output_dir", "./outputs/reports")
    # Clean up the path relative to our current file
    clean_out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', output_dir.strip('./')))
    os.makedirs(clean_out_dir, exist_ok=True)
    
    invoice_no = structured_data.get('invoice_no', 'UNKNOWN_INVOICE')
    
    # Save JSON Report
    json_path = os.path.join(clean_out_dir, f"{invoice_no}_report.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=4)
        
    # Save HTML Report
    html_path = os.path.join(clean_out_dir, f"{invoice_no}_report.html")
    html_content = f"""
    <html>
    <head><title>Audit Report: {invoice_no}</title></head>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2>Invoice Audit Report: {invoice_no}</h2>
        <h3 style="color: {'green' if recommendation == 'Approve' else 'red'};">Recommendation: {recommendation}</h3>
        <p><strong>Discrepancy Summary:</strong> {summary_text}</p>
        <hr>
        <h4>Extracted Data:</h4>
        <pre style="background-color: #f4f4f4; padding: 10px;">{json.dumps(structured_data, indent=2)}</pre>
    </body>
    </html>
    """
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"   --> 📝 Success! Reports saved to: {clean_out_dir}")
    return final_report