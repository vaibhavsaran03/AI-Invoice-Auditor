import os
import time
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from langgraph_workflow.workflow import app

INCOMING_FOLDER = "data/incoming"

def start_monitoring():
    print(f" Monitor Agent: I am watching the '{INCOMING_FOLDER}' folder for new invoices...")
    
    # need a memory bank to remember which files we already processed.
    # Otherwise, it will process the same invoice a million times!
    processed_files = set()

    
    while True:
        # Look at all the files currently inside the incoming folder
        current_files = os.listdir(INCOMING_FOLDER)
        
        for file_name in current_files:
            # only care about specific invoice files: PDF, DOCX, or PNG
            if file_name.endswith(('.pdf', '.docx', '.png')):
                
                # Check if we have already seen this file
                if file_name not in processed_files:
                    print(f"\nBEEP BEEP! NEW INVOICE DETECTED: {file_name} ")
                    print(" Monitor Agent: GO! Passing the invoice to the LangGraph track...")
                    
                   
                    file_path = os.path.join(INCOMING_FOLDER, file_name)
                    initial_backpack = {"file_path": file_path}
                    
                   
                    try:
                        config = {"configurable": {"thread_id": file_name}}
                        
                        app.invoke(initial_backpack, config=config)
                    except Exception as e:
                        print(f" Oops, something went wrong in the workflow: {e}")
                    
                    # Add it to our memory so we don't process it again
                    processed_files.add(file_name)
                    print(f"Finished processing {file_name}. Going back to watching...\n")
        
        
        time.sleep(5)

if __name__ == "__main__":
    os.makedirs(INCOMING_FOLDER, exist_ok=True)
    
    start_monitoring()