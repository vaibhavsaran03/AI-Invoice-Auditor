from typing import TypedDict
from langgraph.graph import StateGraph, END
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except (ImportError, ModuleNotFoundError):
    from langgraph_checkpoint_sqlite import SqliteSaver
import sqlite3
# Import all of our real AI Agents!
from agents.extractor_agent import extract_invoice_data
from agents.translator_agent import translate_invoice
from agents.validation_agent import validate_invoice
from agents.business_validation_agent import validate_business_rules
from agents.reporting_agent import generate_report

# ---------------------------------------------------------
# 1. THE BACKPACK (The State)
# ---------------------------------------------------------
class InvoiceState(TypedDict):
    file_path: str
    extracted_text: str
    translated_text: str
    translation_confidence: float 
    structured_data: dict         
    validation_errors: list       
    erp_validation_errors: list   
    final_report: dict  # <-- Make sure this is a dict!

# ---------------------------------------------------------
# 2. THE RUNNERS (The Nodes)
# ---------------------------------------------------------
def extractor_node(state: InvoiceState):
    return {"extracted_text": extract_invoice_data(state["file_path"])}

def translator_node(state: InvoiceState):
    result = translate_invoice(state["extracted_text"])
    return {
        "translated_text": result.get("translated_text", ""),
        "translation_confidence": result.get("confidence_score", 0.0)
    }

def validator_node(state: InvoiceState):
    result = validate_invoice(state["translated_text"])
    return {
        "structured_data": result.get("structured_data", {}),
        "validation_errors": result.get("errors", [])
    }

def business_validator_node(state: InvoiceState):
    erp_errors = validate_business_rules(state["structured_data"])
    return {"erp_validation_errors": erp_errors}

def reporter_node(state: InvoiceState):
    report = generate_report(
        state["structured_data"], 
        state["validation_errors"], 
        state["erp_validation_errors"],
        state.get("translation_confidence", 1.0) # <--- ADD THIS
    )
    return {"final_report": report}

# --- NEW: The Human Review Placeholder ---
def human_review_node(state: InvoiceState):
    print("👩‍💻 Human Auditor: I have reviewed and fixed the errors. Resuming the race!")
    # The UI will update the state before this node runs, so we just pass it along!
    return state

# --- NEW: The Referee (Conditional Routing) ---
def route_after_reporting(state: InvoiceState):
    recommendation = state.get("final_report", {}).get("recommendation", "Approve")
    if recommendation in ["Manual Review", "Reject"]:
        print("\n🛑 REFEREE: Errors found! Pausing the graph and calling the Human!")
        return "human_review"
    
    print("\n✅ REFEREE: Perfect invoice! Sending straight to the finish line.")
    return END

# ---------------------------------------------------------
# 3. THE TRACK (The Graph)
# ---------------------------------------------------------
workflow = StateGraph(InvoiceState)

# Add all runners
workflow.add_node("extractor", extractor_node)
workflow.add_node("translator", translator_node)
workflow.add_node("validator", validator_node)
workflow.add_node("business_validator", business_validator_node)
workflow.add_node("reporter", reporter_node)
workflow.add_node("human_review", human_review_node)

# Connect the standard relay race
workflow.set_entry_point("extractor")
workflow.add_edge("extractor", "translator")
workflow.add_edge("translator", "validator")
workflow.add_edge("validator", "business_validator")
workflow.add_edge("business_validator", "reporter")

# Add the fork in the road!
workflow.add_conditional_edges("reporter", route_after_reporting)
workflow.add_edge("human_review", END) # <-- Later, this will go to the RAG Indexing Agent!

# --- NEW: Add the Save Game Database and the Pause Button! ---
# Open a direct connection to the database file
conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
memory = SqliteSaver(conn)

app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["human_review"] # <-- The graph will FREEZE before this node runs!
)