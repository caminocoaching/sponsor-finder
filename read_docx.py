
import zipfile
import xml.etree.ElementTree as ET

def get_docx_text(path):
    try:
        with zipfile.ZipFile(path) as document:
            xml_content = document.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            
            text_parts = []
            # Find all text nodes in the docx xml namespaced structure
            for node in tree.iter():
                if node.tag.endswith('}t'):
                    if node.text:
                        text_parts.append(node.text)
                elif node.tag.endswith('}p'):
                    text_parts.append('\n') # New line for paragraphs
                    
            return "".join(text_parts)
    except Exception as e:
        return f"Error reading docx: {e}"

if __name__ == "__main__":
    print(get_docx_text("/Users/camino/Documents/Sponsor Finder/Sponsorship_Response_Templates.docx"))
