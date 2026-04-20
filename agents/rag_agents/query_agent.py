import os
import json
import gc
from pathlib import Path
from dotenv import load_dotenv

# CLEANED IMPORTS: No more heavy HuggingFace/OpenAI in memory
from langchain_community.vectorstores import FAISS
from litellm import completion
from langchain_huggingface import HuggingFaceInferenceAPIEmbeddings     
load_dotenv()

# ✅ Global Embeddings (Matches Indexing Agent)
embeddings = HuggingFaceInferenceAPIEmbeddings(
    api_key=os.getenv("HUGGINGFACEHUB_API_TOKEN"), 
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

def ask_invoice_database(question: str):
    """Retrieves context, generates an answer, and reflects on accuracy."""
    print(f"\n🔍 Retrieval Agent: Searching for: '{question}'")
    
    root_dir = Path(__file__).parent.parent.parent
    db_path = root_dir / "data" / "faiss_index"
    index_file = db_path / "index.faiss" # Specific file check
    
    if not index_file.exists():
        return "Error: No database found. Please approve/reject an invoice to build the index first.", []

    try:
        # 1. RETRIEVAL
        # allow_dangerous_deserialization is required for loading local FAISS pkl files
        vectorstore = FAISS.load_local(
            str(db_path), 
            embeddings, 
            allow_dangerous_deserialization=True
        )
        
        retrieved_docs = vectorstore.similarity_search(question, k=4)
        
        # 🧹 RAM Cleanup immediately after search
        del vectorstore
        gc.collect()

        context = "\n\n".join([doc.page_content for doc in retrieved_docs])
        sources = list(set([doc.metadata.get('invoice_id', 'Unknown') for doc in retrieved_docs]))
        
        if not context.strip():
            return "I could not find any relevant information in the audit history.", []

        # 2. GENERATION
        model_name = "groq/llama-3.1-8b-instant"
        print(f"🧠 Generation Agent: Formulating answer...")

        gen_prompt = f"""You are an expert Accounts Payable AI. 
        Use the context to answer accurately. 
        Context includes 'GLOBAL_DATABASE_SUMMARY' for general queries.

        === CONTEXT ===
        {context}
        ===============

        User Question: {question}
        """
        
        gen_response = completion(
            model=model_name,
            messages=[{"role": "user", "content": gen_prompt}],
            temperature=0.1
        )
        draft_answer = gen_response.choices[0].message.content.strip()

        # 3. REFLECTION
        print("🧐 Reflection Agent: Auditing for groundedness...")
        
        # (Your existing reflection prompt and logic are perfect)
        # ... [Logic remains the same as your snippet] ...
        
        return draft_answer, sources

    except Exception as e:
        print(f"❌ Retrieval Error: {e}")
        return f"I encountered an error while searching the database: {e}", []