import PyPDF2
from typing import Dict, Any
import os

class PDFAnalyzer:
    """Service for extracting and analyzing text from PDF pitch decks."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        
    def extract_text(self) -> str:
        """Extract text content from PDF file."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"PDF file not found at {self.file_path}")
            
        text_content = ""
        try:
            with open(self.file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text_content += page.extract_text() + "\n\n"
            return text_content
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
    
    def extract_sections(self) -> Dict[str, str]:
        """
        Extract and categorize different sections of the pitch deck.
        Returns a dictionary with categorized content.
        """
        text = self.extract_text()
        
        # Initialize sections dictionary
        sections = {
            'technical': '',
            'market': '',
            'team': '',
            'financial': '',
            'risks': ''
        }
        
        # TODO: Implement more sophisticated section detection
        # For now, we'll return all text in each section for AI analysis
        for section in sections:
            sections[section] = text
            
        return sections 