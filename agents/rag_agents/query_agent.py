import os
import json
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from litellm import completion

load_dotenv()

def ask_invoice_database(question: str):
    """Retrieves context, generates an answer, and reflects on accuracy with citations."""
    print(f"\n🔍 Retrieval Agent: Searching for: '{question}'")
    
    root_dir = Path(__file__).parent.parent.parent
    db_path = root_dir / "data" / "faiss_index"
    
    if not db_path.exists():
        return "Error: No database found. Please run the Indexing Agent first.", []

    # 1. RETRIEVAL (Fetching top 4 chunks for better global context)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = FAISS.load_local(str(db_path), embeddings, allow_dangerous_deserialization=True)
    
    retrieved_docs = vectorstore.similarity_search(question, k=4)
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])
    sources = list(set([doc.metadata.get('source', 'Unknown') for doc in retrieved_docs]))
    
    if not context.strip():
        return "I could not find any relevant information.", []

    # 2. GENERATION
    model_name = "groq/llama-3.1-8b-instant"
    print(f"🧠 Generation Agent: Formulating answer...")

    gen_prompt = f"""You are an expert Accounts Payable AI. 
    Use the following retrieved context to answer the user's question.
    If the question is a general summary (e.g., "list invoices"), use the GLOBAL_DATABASE_SUMMARY if available.

    === CONTEXT ===
    {context}
    ===============

    User Question: {question}
    """
    
    try:
        gen_response = completion(
            model=model_name,
            messages=[{"role": "user", "content": gen_prompt}],
            temperature=0.1
        )
        draft_answer = gen_response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Generation Error: {e}", []

    # 3. REFLECTION (Now updated to handle summaries properly)
    print("🧐 Reflection Agent: Auditing for groundedness...")
    
    reflect_prompt = f"""You are an AI Quality Control Auditor. 
    Evaluate if the draft answer is grounded in the provided context.
    
    - PASS if the answer uses facts (names, numbers, statuses) found in the context.
    - PASS if the answer summarizes a list provided in the context.
    - FAIL only if the answer mentions specific data NOT present in the context.

    === CONTEXT ===
    {context}
    
    === DRAFT ANSWER ===
    {draft_answer}
    
    Respond ONLY with valid JSON: {{"status": "PASS", "reason": "..."}}
    """
    
    try:
        reflect_response = completion(
            model=model_name,
            messages=[{"role": "user", "content": reflect_prompt}],
            temperature=0.0
        )
        
        clean_json = reflect_response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
        evaluation = json.loads(clean_json)
        
        if evaluation.get("status") == "PASS":
            print("   --> ✅ Reflection PASS")
            return draft_answer, sources
        else:
            print(f"   --> 🚨 Reflection FAIL: {evaluation.get('reason')}")
            return "My quality control systems blocked this answer as it couldn't be fully verified against the reports.", []
            
    except Exception as e:
        return f"Error during reflection: {e}", []