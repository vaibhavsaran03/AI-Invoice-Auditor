import os
import time
import sys

# 1. We need to tell Python how to find our workflow file.
# This little trick adds your main project folder to Python's radar.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now we can import the "app" (our race track) from the workflow file!
from langgraph_workflow.workflow import app

# This is the folder we want to watch
INCOMING_FOLDER = "data/incoming"

def start_monitoring():
    print(f"👀 Monitor Agent: I am watching the '{INCOMING_FOLDER}' folder for new invoices...")
    
    # We need a memory bank to remember which files we already processed.
    # Otherwise, it will process the same invoice a million times!
    processed_files = set()

    # The "while True" loop makes the agent run forever, 24/7.
    while True:
        # Look at all the files currently inside the incoming folder
        current_files = os.listdir(INCOMING_FOLDER)
        
        for file_name in current_files:
            # We only care about specific invoice files: PDF, DOCX, or PNG
            if file_name.endswith(('.pdf', '.docx', '.png')):
                
                # Check if we have already seen this file
                if file_name not in processed_files:
                    print(f"\n🚨 BEEP BEEP! NEW INVOICE DETECTED: {file_name} 🚨")
                    print("🔫 Monitor Agent: GO! Passing the invoice to the LangGraph track...")
                    
                   # 1. Create the starting "backpack" with the file path
                    file_path = os.path.join(INCOMING_FOLDER, file_name)
                    initial_backpack = {"file_path": file_path}
                    
                    # 2. Start the race! Hand it to the graph.
                    try:
                        # NEW: We give this race a unique ID so we can pause/resume it later!
                        config = {"configurable": {"thread_id": file_name}}
                        
                        # Pass the config to the track
                        app.invoke(initial_backpack, config=config)
                    except Exception as e:
                        print(f"❌ Oops, something went wrong in the workflow: {e}")
                    
                    # 3. Add it to our memory so we don't process it again
                    processed_files.add(file_name)
                    print(f"🏁 Finished processing {file_name}. Going back to watching...\n")
        
        # Take a 5-second nap before checking the folder again so we don't fry the computer's brain!
        time.sleep(5)

if __name__ == "__main__":
    # Make sure the incoming folder actually exists before we try to watch it
    os.makedirs(INCOMING_FOLDER, exist_ok=True)
    
    # Start the watchdog!
    start_monitoring()