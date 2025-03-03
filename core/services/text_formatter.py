from typing import Dict, List
import re
from bs4 import BeautifulSoup
import html

class TextFormatter:
    """
    Utility class for formatting and cleaning text content.
    Ensures consistent formatting and removes unwanted symbols and HTML tags.
    """
    
    @staticmethod
    def clean_html(text: str) -> str:
        """
        Removes HTML tags while preserving meaningful whitespace and structure.
        """
        if not text:
            return ""
            
        # First unescape any HTML entities
        text = html.unescape(text)
        
        # Use BeautifulSoup to parse HTML
        soup = BeautifulSoup(text, 'html.parser')
        
        # Handle special elements before stripping tags
        for br in soup.find_all('br'):
            br.replace_with('\n')
        for p in soup.find_all('p'):
            p.append('\n\n')
        
        # Get text content
        text = soup.get_text()
        
        # Clean up whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)  # Replace multiple newlines with double newline
        text = re.sub(r' +', ' ', text)  # Replace multiple spaces with single space
        
        return text.strip()
    
    @staticmethod
    def clean_markdown_headers(text: str) -> str:
        """
        Converts markdown headers to proper format and removes extra symbols.
        """
        # Remove markdown header symbols while preserving the text
        cleaned = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        return cleaned.strip()
    
    @staticmethod
    def format_blog_content(content: str) -> str:
        """
        Formats blog content by:
        1. Removing HTML tags and unnecessary symbols
        2. Applying proper spacing and structure
        3. Ensuring consistent formatting
        4. Adding clear paragraph demarcation
        5. Handling headers and lists properly
        """
        if not content:
            return ""
            
        # First clean HTML
        content = TextFormatter.clean_html(content)
        
        # Handle headers (lines that look like headers)
        lines = content.split('\n')
        formatted_lines = []
        in_list = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                if in_list:
                    in_list = False
                formatted_lines.append('')
                continue
                
            # Check for header-like lines
            if (line.isupper() and len(line) > 3) or line.endswith(':'):
                # Add extra spacing around headers
                if formatted_lines and formatted_lines[-1]:
                    formatted_lines.append('')
                formatted_lines.append(f'<div class="header">{line.upper()}</div>')
                formatted_lines.append('')
                continue
                
            # Check for list items
            if line.startswith(('- ', '* ', '• ', '→ ')):
                if not in_list and formatted_lines and formatted_lines[-1]:
                    formatted_lines.append('')
                in_list = True
                formatted_lines.append(line)
                continue
                
            # Check for numbered lists
            if re.match(r'^\d+\.\s', line):
                if not in_list and formatted_lines and formatted_lines[-1]:
                    formatted_lines.append('')
                in_list = True
                formatted_lines.append(line)
                continue
                
            # Regular paragraph text
            if in_list:
                in_list = False
                formatted_lines.append('')
            
            # Handle sentence spacing
            line = re.sub(r'([.!?])\s*(\w)', r'\1 \2', line)
            
            # If this line starts with a lowercase letter and the previous line wasn't empty,
            # it's probably a continuation of the previous paragraph
            if (formatted_lines and formatted_lines[-1] and line[0].islower() and 
                not line.startswith(('- ', '* ', '• ', '→ ')) and 
                not re.match(r'^\d+\.\s', line)):
                formatted_lines[-1] = formatted_lines[-1] + ' ' + line
            else:
                if formatted_lines and formatted_lines[-1]:
                    formatted_lines.append('')
                formatted_lines.append(line)
        
        # Join lines and clean up multiple newlines
        content = '\n'.join(formatted_lines)
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Ensure proper spacing after punctuation
        content = re.sub(r'([.!?])\s*(\w)', r'\1 \2', content)
        
        # Remove any remaining special characters or unnecessary formatting
        content = re.sub(r'[*_]{3,}', '', content)
        
        return content.strip()
    
    @staticmethod
    def format_title(title: str) -> str:
        """
        Formats titles by:
        1. Removing HTML tags and markdown symbols
        2. Applying proper capitalization
        3. Removing unnecessary spaces
        """
        # Clean HTML and markdown
        title = TextFormatter.clean_html(title)
        title = TextFormatter.clean_markdown_headers(title)
        title = ' '.join(title.split())  # Normalize spaces
        
        # Apply title case while preserving acronyms
        words = title.split()
        formatted_words = []
        
        # List of words that should not be capitalized
        lowercase_words = {'a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor',
                         'on', 'at', 'to', 'from', 'by', 'in', 'of', 'with'}
        
        for i, word in enumerate(words):
            # Check if word is an acronym (all uppercase)
            if word.isupper() and len(word) > 1:
                formatted_words.append(word)
            # Always capitalize first and last word
            elif i == 0 or i == len(words) - 1:
                formatted_words.append(word.capitalize())
            # Don't capitalize certain words unless they're first or last
            elif word.lower() in lowercase_words:
                formatted_words.append(word.lower())
            # Capitalize other words
            else:
                formatted_words.append(word.capitalize())
        
        return ' '.join(formatted_words)
    
    @staticmethod
    def format_meta_description(description: str) -> str:
        """
        Formats meta descriptions by:
        1. Removing HTML and markdown
        2. Ensuring proper length
        3. Maintaining sentence structure
        """
        # Clean HTML and normalize text
        description = TextFormatter.clean_html(description)
        description = TextFormatter.clean_markdown_headers(description)
        
        # Normalize spaces
        description = ' '.join(description.split())
        
        # Truncate to recommended SEO length (155 characters) if needed
        if len(description) > 155:
            description = description[:152] + '...'
        
        return description.strip()
    
    @staticmethod
    def format_keywords(keywords: str) -> str:
        """
        Formats keywords by:
        1. Removing HTML and special characters
        2. Ensuring proper separator format
        3. Removing duplicates
        """
        # Clean HTML first
        keywords = TextFormatter.clean_html(keywords)
        
        # Split keywords by common separators
        keyword_list = re.split(r'[,;|]', keywords)
        
        # Clean individual keywords
        cleaned_keywords = []
        for keyword in keyword_list:
            # Remove special characters and extra spaces
            cleaned = re.sub(r'[^\w\s-]', '', keyword)
            cleaned = cleaned.strip().lower()
            if cleaned and cleaned not in cleaned_keywords:
                cleaned_keywords.append(cleaned)
        
        # Join with standard separator
        return ', '.join(cleaned_keywords)
    
    @staticmethod
    def format_excerpt(content: str, max_length: int = 200) -> str:
        """
        Creates a clean excerpt from content by:
        1. Removing HTML and markdown
        2. Truncating to specified length
        3. Ensuring it ends with a complete sentence
        """
        # Clean the content first
        content = TextFormatter.clean_html(content)
        content = TextFormatter.clean_markdown_headers(content)
        
        # If content is shorter than max_length, return it as is
        if len(content) <= max_length:
            return content.strip()
        
        # Find the last sentence boundary within max_length
        truncated = content[:max_length]
        last_sentence = re.search(r'.*[.!?]', truncated)
        
        if last_sentence:
            return last_sentence.group(0).strip()
        
        # If no sentence boundary found, find the last word boundary
        last_word = re.search(r'.*\s', truncated)
        if last_word:
            return last_word.group(0).strip() + '...'
        
        return truncated.strip() + '...' 