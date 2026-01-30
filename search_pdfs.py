import os
import pdfplumber

def search(query):
    print(f"--- Searching for: {query} ---")
    files = [f for f in os.listdir('.') if f.endswith('.pdf')]
    for file in files:
        try:
            with pdfplumber.open(file) as pdf:
                for i, p in enumerate(pdf.pages):
                    text = p.extract_text() or ""
                    if query.lower() in text.lower():
                        print(f"FOUND in {file} (Page {i+1}):")
                        # Print context
                        lines = text.split('\n')
                        for line in lines:
                            if query.lower() in line.lower():
                                print(f"  > {line.strip()}")
        except:
            pass

if __name__ == "__main__":
    search("Module 1")
    search("Social Media Audit")
    search("Product Worksheet")
