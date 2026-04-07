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
    
    if not db_sqlite_path.exists(): return

    documents = []
    all_invoice_nos = []
    invoice_summaries = []

    try:
        conn = sqlite3.connect(str(db_sqlite_path))
        cursor = conn.cursor()
        cursor.execute("SELECT invoice_id, status, comment, data, system_errors FROM audit_history")
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            inv_id, status, comment, data_raw, sys_errors = row
            details = json.loads(data_raw)
            
            vendor = details.get('vendor_name') or details.get('vendor_id', 'Unknown')
            inv_no = details.get('invoice_no', inv_id)
            
            all_vendors.add(vendor)
            all_invoice_nos.append(inv_no)
            invoice_summaries.append(f"Invoice {inv_no} ({status}): {comment}")

            # 🌟 RICH CONTEXT CHUNK: Combines AI findings with Human feedback
            content = f"METADATA_TAG: SINGLE_INVOICE_DETAILS\n"
            content += f"Invoice: {inv_no}\n"
            content += f"Vendor: {vendor}\n"
            content += f"Audit Status: {status.upper()}\n"
            content += f"AI DETECTED DISCREPANCIES: {sys_errors if sys_errors else 'None'}\n"
            content += f"AUDITOR NOTE: {comment}\n"
            content += f"Amount: {details.get('total_amount')} {details.get('currency', 'EUR')}\n"
            content += f"Line Items: {json.dumps(details.get('line_items', []))}"
            
            doc = Document(page_content=content, metadata={"source": inv_id, "type": "detail"})
            documents.append(doc)

    except Exception as e:
        print(f"❌ Error during Indexing: {e}")
        return

    # 2. Update Global Summary
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

if __name__ == "__main__":
    index_reports()