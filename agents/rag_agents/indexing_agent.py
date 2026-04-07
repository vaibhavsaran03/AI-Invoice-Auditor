import json
import sqlite3
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

def index_reports():
    """Reads from audit_history SQLite table and saves to a FAISS Vector Database."""
    print("📚 Indexing Agent: Syncing RAG with Intelligent Audit Context...")
    
    current_file = Path(__file__).resolve()
    root_dir = current_file.parent.parent.parent 
    db_sqlite_path = root_dir / "checkpoints.sqlite"
    faiss_db_path = root_dir / "data" / "faiss_index"
    
    if not db_sqlite_path.exists(): 
        print("🚨 SQLite database file does not exist yet. Skipping indexing.")
        return

    # Initialize variables at the top level
    documents = []
    all_vendors = set()
    all_invoice_nos = []
    invoice_summaries = []

    try:
        conn = sqlite3.connect(str(db_sqlite_path))
        cursor = conn.cursor()
        
        # Check if table exists before querying
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_history'")
        if not cursor.fetchone():
            print("🚨 Table 'audit_history' not found. Audit an invoice first!")
            conn.close()
            return

        cursor.execute("SELECT invoice_id, status, comment, data, system_errors FROM audit_history")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print("📝 No rows found in audit_history. Nothing to index.")
            return

        for row in rows:
            inv_id, status, comment, data_raw, sys_errors = row
            details = json.loads(data_raw)
            
            vendor = details.get('vendor_name') or details.get('vendor_id', 'Unknown')
            inv_no = details.get('invoice_no', inv_id)
            
            all_vendors.add(vendor)
            all_invoice_nos.append(inv_no)
            invoice_summaries.append(f"Invoice {inv_no} ({status}): {comment}")

            content = f"METADATA_TAG: SINGLE_INVOICE_DETAILS\n"
            content += f"Invoice: {inv_no}\nVendor: {vendor}\nAudit Status: {status.upper()}\n"
            content += f"AI DETECTED DISCREPANCIES: {sys_errors if sys_errors else 'None'}\n"
            content += f"AUDITOR NOTE: {comment}\n"
            
            doc = Document(page_content=content, metadata={"source": inv_id, "type": "detail"})
            documents.append(doc)

        # 2. Update Global Summary (STAY INSIDE TRY BLOCK)
        if documents:
            summary_content = "METADATA_TAG: GLOBAL_DATABASE_SUMMARY\n"
            summary_content += f"Total Audited: {len(all_invoice_nos)}\n"
            summary_content += f"Vendors: {', '.join(list(all_vendors))}\n"
            summary_content += f"Audit Log: {'; '.join(invoice_summaries)}"
            
            documents.append(Document(page_content=summary_content, metadata={"type": "summary"}))

            # 3. FAISS Update
            embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            vectorstore = FAISS.from_documents(documents, embeddings)
            faiss_db_path.mkdir(parents=True, exist_ok=True)
            vectorstore.save_local(str(faiss_db_path))
            print(f"✅ RAG Sync Complete! Audited knowledge is now live.")

    except Exception as e:
        print(f"❌ Error during Indexing: {e}")
if __name__ == "__main__":
    index_reports()