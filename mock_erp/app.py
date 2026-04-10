import json
import os
import shutil
import sqlite3
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# AI Logic Imports
from langgraph_workflow.workflow import app as langgraph_app
from agents.rag_agents.indexing_agent import index_reports
from agents.rag_agents.query_agent import ask_invoice_database

app = FastAPI(title="Agentic AI Enterprise Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
ROOT_DIR = Path(__file__).parent.parent.resolve()
INCOMING_DIR = ROOT_DIR / "data" / "incoming"
INCOMING_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DB = ROOT_DIR / "checkpoints.sqlite"

def init_db():
    conn = sqlite3.connect(str(CHECKPOINT_DB))
    cursor = conn.cursor()
    # 🌟 Added system_errors column to existing table logic
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_history (
            invoice_id TEXT PRIMARY KEY,
            status TEXT,
            comment TEXT,
            system_errors TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            data JSON
        )
    """)
    conn.commit()
    conn.close()

def save_audit_record(invoice_id, status, comment, data, system_errors=None):
    try:
        conn = sqlite3.connect(str(CHECKPOINT_DB))
        cursor = conn.cursor()
        # Convert list of errors to string for SQL storage
        error_str = ", ".join(system_errors) if isinstance(system_errors, list) else (system_errors or "")
        cursor.execute(
            "INSERT OR REPLACE INTO audit_history (invoice_id, status, comment, system_errors, data) VALUES (?, ?, ?, ?, ?)",
            (invoice_id, status, comment, error_str, json.dumps(data))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ DB Log Error: {e}")

init_db()

@app.post("/api/process/{filename}")
async def process_invoice(filename: str):
    file_path = INCOMING_DIR / filename
    if not file_path.exists(): raise HTTPException(status_code=404, detail="File not found")
    
    config = {"configurable": {"thread_id": filename}}
    try:
        state_values = langgraph_app.invoke({"file_path": str(file_path)}, config=config)
        current_state = langgraph_app.get_state(config)
        errors = state_values.get("erp_validation_errors", [])
        
        if current_state.next and "human_review" in current_state.next:
            # 🌟 Save current errors to DB so they aren't lost during the pause
            save_audit_record(filename, "pending", "Waiting for Review", state_values.get("structured_data", {}), errors)
            return {
                "status": "paused",
                "errors": errors,
                "data": state_values.get("structured_data", {})
            }
        
        # Auto-Approve path
        save_audit_record(filename, "approved", "Auto-approved by AI System", state_values.get("structured_data", {}), errors)

        index_reports()
        
        return {"status": "complete", "recommendation": "Approved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline Error: {str(e)}")

@app.post("/api/hitl-action/{thread_id}")
async def handle_hitl_action(thread_id: str, payload: dict):
    config = {"configurable": {"thread_id": thread_id}}
    action = payload.get("action") 
    updated_data = payload.get("data")
    comment = payload.get("comment", "No comment.")
    
    try:
        # 🌟 Fetch the original AI errors from state to include in the permanent record
        state = langgraph_app.get_state(config)
        original_errors = state.values.get("erp_validation_errors", [])

        save_audit_record(thread_id, action, comment, updated_data, original_errors)
        
        langgraph_app.update_state(config, {
            "structured_data": updated_data,
            "final_report": {
                "recommendation": f"{action.capitalize()} (Note: {comment})", 
                "discrepancy_summary": f"Final Status: {action}. Auditor: {comment}"
            }
        })
        langgraph_app.invoke(None, config=config)
        index_reports() # Re-sync RAG with the new decision
        return {"message": f"Invoice {action}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audit-stats")
async def get_audit_stats():
    try:
        conn = sqlite3.connect(str(CHECKPOINT_DB))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM audit_history WHERE status = 'approved'")
        count = cursor.fetchone()[0]
        conn.close()
        return {"approved": count}
    except: return {"approved": 0}

@app.get("/api/hitl-queue")
async def get_hitl_queue():
    paused_threads = []
    try:
        conn = sqlite3.connect(str(CHECKPOINT_DB))
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints")
        threads = cursor.fetchall()
        for (tid,) in threads:
            state = langgraph_app.get_state({"configurable": {"thread_id": tid}})
            if state.next and "human_review" in state.next:
                paused_threads.append(tid)
        conn.close()
    except: return {"queue": []}
    return {"queue": paused_threads}

@app.get("/api/hitl-details/{thread_id}")
async def get_hitl_details(thread_id: str):
    state = langgraph_app.get_state({"configurable": {"thread_id": thread_id}})
    return {"errors": state.values.get("erp_validation_errors", []), "data": state.values.get("structured_data", {})}

@app.post("/api/upload")
async def upload_invoice(file: UploadFile = File(...)):
    file_path = INCOMING_DIR / file.filename
    with file_path.open("wb") as buffer: shutil.copyfileobj(file.file, buffer)
    return {"message": "Uploaded", "filename": file.filename}

@app.post("/api/chat")
async def chat_with_db(request: dict):
    query = request.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    answer, sources = ask_invoice_database(query)
    return {"answer": answer, "sources": sources}

@app.get("/api/rejected-history")
async def get_rejected_history():
    try:
        conn = sqlite3.connect(str(CHECKPOINT_DB))
        cursor = conn.cursor()
        cursor.execute("SELECT invoice_id, status, comment, timestamp FROM audit_history WHERE status = 'rejected' ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        conn.close()
        return [{"id": r[0], "date": r[3], "comment": r[2]} for r in rows]
    except: return []

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("mock_erp.app:app", host="0.0.0.0", port=port, reload=False)