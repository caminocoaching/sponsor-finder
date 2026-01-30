
import pypdf

def extract_text_from_pdf(pdf_path):
    try:
        reader = pypdf.PdfReader(pdf_path)
        text = ""
        for i, page in enumerate(reader.pages):
            try:
                content = page.extract_text()
                if content:
                    text += f"\n--- PAGE {i+1} ---\n{content}"
            except Exception as e:
                print(f"⚠️ Error on page {i+1}: {e}")
        
        print(text)
    except Exception as e:
        print(f"Error opening PDF: {e}")

if __name__ == "__main__":
    extract_text_from_pdf("YES-GENERATING MOTORSPORT SPONSORSHIP PROPOSAL.pdf")
