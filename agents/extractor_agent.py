import os
import pdfplumber
import docx
import pytesseract
from PIL import Image

def extract_invoice_data(file_path: str) -> str:
    """
    This function looks at the file type and reads the text inside it.
    """
    print(f"🕵️ Extractor Agent: Putting on my reading glasses for {file_path}...")
    
    extracted_text = ""
    
    try:
        # If it's a PDF file
        if file_path.endswith('.pdf'):
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    # Extract text from each page
                    page_text = page.extract_text()
                    if page_text:
                        extracted_text += page_text + "\n"
                        
        # If it's a Word Document
        elif file_path.endswith('.docx'):
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                extracted_text += para.text + "\n"
                
        # If it's an Image (PNG)
        elif file_path.endswith('.png'):
            try:
                print("🖼️ Oh, an image! Using OCR to read it...")
                image = Image.open(file_path)
                extracted_text = pytesseract.image_to_string(image)
            except Exception as ocr_error:
                print(f"⚠️ OCR Error: Tesseract engine not found on server. {ocr_error}")
                extracted_text = "Error: OCR is not configured on this server environment."
            
        else:
            extracted_text = "Error: I don't know how to read this file type!"

        print("🕵️ Extractor Agent: Done reading! Here is a sneak peek of what I found:")
        # Print just the first 100 characters so we don't flood the terminal
        print(f"   --> '{extracted_text[:100]}...'")
        
        return extracted_text

    except Exception as e:
        print(f"❌ Extractor Agent Error: Could not read the file. Reason: {e}")
        return ""