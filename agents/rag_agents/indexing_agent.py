import json
import os
import sqlite3
import gc
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceInferenceAPIEmbeddings
from langchain_core.documents import Document


def get_embeddings():
    return HuggingFaceInferenceAPIEmbeddings(
        api_key=os.getenv("HUGGINGFACEHUB_API_TOKEN"),
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


def index_reports():
    print("📚 Indexing Agent: Incremental RAG update...")

    current_file = Path(__file__).resolve()
    root_dir = current_file.parent.parent.parent
    db_sqlite_path = root_dir / "checkpoints.sqlite"
    faiss_db_path = root_dir / "data" / "faiss_index"
    index_file = faiss_db_path / "index.faiss"

    if not db_sqlite_path.exists():
        print("🚨 No DB found. Skipping indexing.")
        return

    try:
        conn = sqlite3.connect(str(db_sqlite_path))
        cursor = conn.cursor()

        cursor.execute("SELECT invoice_id, status, comment, data, system_errors FROM audit_history")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print("📝 Nothing to index.")
            return

        embeddings = get_embeddings()

        # ✅ LOAD EXISTING INDEX + GET EXISTING IDS
        existing_ids = set()

        if index_file.exists():
            print("🔄 Loading existing FAISS index...")
            vectorstore = FAISS.load_local(
                str(faiss_db_path),
                embeddings,
                allow_dangerous_deserialization=True
            )

            try:
                existing_docs = vectorstore.docstore._dict.values()
                existing_ids = set(doc.metadata.get("invoice_id") for doc in existing_docs)
            except Exception:
                print("⚠️ Could not read docstore, skipping dedup")
        else:
            print("🆕 Creating new FAISS index...")
            vectorstore = None

        # 🔥 STEP 1: CHECK IF REBUILD IS REQUIRED
        rebuild_required = False

        for row in rows:
            inv_id = row[0]
            if inv_id in existing_ids:
                print(f"🔄 Update detected for {inv_id}, triggering rebuild...")
                rebuild_required = True
                break

        # 🔥 STEP 2: DECIDE DATA TO INDEX
        if rebuild_required:
            print("♻️ Rebuilding FAISS with ALL records...")
            rows_to_index = rows
            vectorstore = None  # force rebuild
        else:
            rows_to_index = rows[-5:]  # incremental

        documents = []

        for row in rows_to_index:
            inv_id, status, comment, data_raw, sys_errors = row

            # 🚫 Skip duplicates ONLY if NOT rebuilding
            if not rebuild_required and inv_id in existing_ids:
                continue

            try:
                details = json.loads(data_raw)
            except Exception:
                print(f"⚠️ Skipping invalid JSON for {inv_id}")
                continue

            vendor = details.get('vendor_name') or details.get('vendor_id', 'Unknown')
            inv_no = details.get('invoice_no', inv_id)

            content = (
                f"Invoice: {inv_no}\n"
                f"Vendor: {vendor}\n"
                f"Status: {status}\n"
                f"Errors: {sys_errors or 'None'}\n"
                f"Comment: {comment}"
            )

            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "invoice_id": inv_id,
                        "status": status
                    }
                )
            )

        if not documents:
            print("⚠️ No new documents to add.")
            return

        documents = documents[:50]

        # ✅ BUILD OR UPDATE
        if vectorstore:
            print("➕ Adding new documents to FAISS...")
            vectorstore.add_documents(documents)
        else:
            print("🆕 Building FAISS from scratch...")
            vectorstore = FAISS.from_documents(documents, embeddings)

        # ✅ SAVE
        faiss_db_path.mkdir(parents=True, exist_ok=True)
        vectorstore.save_local(str(faiss_db_path))

        # 🧹 CLEAN MEMORY
        del vectorstore
        del documents
        gc.collect()

        print("✅ FAISS updated successfully!")

    except Exception as e:
        print(f"❌ Indexing Error: {e}")


if __name__ == "__main__":
    index_reports()