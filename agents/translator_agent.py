import os
import json
from dotenv import load_dotenv
from litellm import completion

load_dotenv()

def translate_invoice(extracted_text: str) -> dict:
    """
    Translates text to English AND calculates an AI confidence score.
    """
    print("🧠 Translator Agent: Translating and calculating confidence score...")
    
    if not extracted_text.strip():
        return {"translated_text": "Error: No text provided.", "confidence_score": 0.0}

    # We now prompt the AI to output JSON containing BOTH the text and the score
    messages = [
        {
            "role": "system", 
            "content": "You are an expert multilingual logistics translator. Translate the invoice text to English. Respond ONLY with a valid JSON object containing two keys: 'translated_text' (the full English translation) and 'confidence_score' (a float between 0.0 and 1.0 representing your confidence in the translation). Do not add any markdown formatting or conversation."
        },
        {
            "role": "user", 
            "content": f"Here is the invoice text:\n\n{extracted_text}"
        }
    ]

    try:
        response = completion(
            model="groq/llama-3.1-8b-instant",
            messages=messages,
            temperature=0.1
        )
        
        raw_output = response.choices[0].message.content
        clean_json = raw_output.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_json)
        
        print(f"   --> 🌐 Translation complete! Confidence Score: {result.get('confidence_score')}")
        return result

    except Exception as e:
        print(f"❌ AI Translation Error: {e}")
        return {"translated_text": extracted_text, "confidence_score": 0.0}