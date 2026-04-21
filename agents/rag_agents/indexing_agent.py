import json
import os
import sqlite3
import gc
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from dotenv import load_dotenv

load_dotenv()

def get_embeddings():
    api_key = os.getenv("HUGGINGFACEHUB_API_TOKEN")
    return HuggingFaceEndpointEmbeddings(
        model="sentence-transformers/all-MiniLM-L6-v2",
        huggingfacehub_api_token=api_key,
        task="feature-extraction"
    )

def index_reports():
    print("Indexing Agent: Incremental RAG update...")

    current_file = Path(__file__).resolve()
    root_dir = current_file.parent.parent.parent
    db_sqlite_path = root_dir / "checkpoints.sqlite"
    faiss_db_path = root_dir / "data" / "faiss_index"
    index_file = faiss_db_path / "index.faiss"

    if not db_sqlite_path.exists():
        print("No DB found. Skipping indexing.")
        return

    try:
        conn = sqlite3.connect(str(db_sqlite_path))
        cursor = conn.cursor()
        
        # To check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_history'")
        if not cursor.fetchone():
            print(" Table 'audit_history' not found.")
            conn.close()
            return

        cursor.execute("SELECT invoice_id, status, comment, data, system_errors FROM audit_history")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print(" Nothing to index.")
            return

        embeddings = get_embeddings()
        existing_ids = set()
        vectorstore = None

        # LOAD EXISTING INDEX
        if index_file.exists():
            print("🔄 Loading existing FAISS index...")
            vectorstore = FAISS.load_local(
                str(faiss_db_path),
                embeddings,
                allow_dangerous_deserialization=True
            )
            # Efficiently extract IDs from docstore
            existing_ids = set(doc.metadata.get("invoice_id") for doc in vectorstore.docstore._dict.values())
        else:
            print("Creating new FAISS index...")

        # DETERMINE NEW DOCUMENTS
        documents = []
        for row in rows:
            inv_id, status, comment, data_raw, sys_errors = row
            if inv_id in existing_ids: continue

            try:
                details = json.loads(data_raw)
                
                # --- NEW: Extract Deep Details ---
                vendor = details.get('vendor_name') or details.get('vendor_id', 'Unknown')
                inv_no = details.get('invoice_no', inv_id)
                currency = details.get('currency', '$')
                total = details.get('total_amount', 0)
                
                # Detailed Line Items
                line_items = details.get('line_items', [])
                items_str = "\n".join([
                    f"- {item.get('description')} | SKU: {item.get('item_code')} | Qty: {item.get('qty')} | Price: {item.get('unit_price')}" 
                    for item in line_items
                ])

                # Build the "Full Knowledge" Document
                content = (
                    f"INVOICE RECORD\n"
                    f"Number: {inv_no}\n"
                    f"Vendor: {vendor}\n"
                    f"Total: {currency}{total}\n"
                    f"Status: {status}\n"
                    f"Decision Comment: {comment}\n"
                    f"System Flags/Errors: {sys_errors or 'None'}\n\n"
                    f"LINE ITEM BREAKDOWN:\n{items_str}\n"
                    f"------------------------"
                )

                documents.append(
                    Document(
                        page_content=content,
                        metadata={"invoice_id": inv_id, "status": status, "vendor": vendor}
                    )
                )
            except Exception as e:
                print(f"Error parsing {inv_id}: {e}")
                continue

        # UPDATE FAISS
        if not documents:
            print(" No new documents found. RAG is up to date.")
            return

        if vectorstore:
            print(f"Adding {len(documents)} new documents...")
            vectorstore.add_documents(documents)
        else:
            print(f" Building fresh index with {len(documents)} documents...")
            vectorstore = FAISS.from_documents(documents, embeddings)

        # SAVE & PURGE RAM
        faiss_db_path.mkdir(parents=True, exist_ok=True)
        vectorstore.save_local(str(faiss_db_path))

        # Crucial for 512MB RAM limit
        del vectorstore
        del documents
        gc.collect()

        print("FAISS updated successfully!")

    except Exception as e:
        print(f"Indexing Error: {e}")

if __name__ == "__main__":
    index_reports()