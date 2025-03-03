import requests
from bs4 import BeautifulSoup
from django.conf import settings
from openai import OpenAI
from typing import Dict, Optional
from .text_formatter import TextFormatter

class BlogGenerator:
    """Service for generating blog content from URLs using AI"""
    
    def __init__(self):
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OpenAI API key is not configured. Please set OPENAI_API_KEY in your environment variables.")
        self.client = OpenAI(api_key=api_key)
        self.formatter = TextFormatter()
    
    def generate_blog_post(self, source_url: str, word_count: int = 500) -> Dict:
        """
        Generate a blog post from a source URL using AI.
        Returns a dictionary containing the generated content and meta information.
        """
        try:
            # Fetch and extract content from source URL
            article_text = self._fetch_url_content(source_url)
            
            # Generate main content
            content = self._generate_content(article_text, word_count)
            
            # Generate meta information
            meta_info = self._generate_meta_info(content)
            
            return {
                'content': content,
                'title': meta_info.get('title', ''),
                'description': meta_info.get('description', ''),
                'keywords': meta_info.get('keywords', '')
            }
            
        except ValueError as e:
            raise ValueError(f"API Configuration Error: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to generate blog post: {str(e)}")
    
    def _fetch_url_content(self, url: str) -> str:
        """Fetch and extract main content from URL"""
        try:
            # Validate URL format
            if not url.startswith(('http://', 'https://')):
                raise ValueError("URL must start with http:// or https://")

            # Handle Google News URLs
            if 'news.google.com' in url:
                raise ValueError(
                    "Google News URLs cannot be processed directly. Please use the original article URL instead. "
                    "You can find this by clicking the article title in Google News to go to the source website."
                )

            # Add headers to mimic a browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }

            # Fetch content with timeout and headers
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not ('text/html' in content_type or 'application/xhtml+xml' in content_type):
                raise ValueError(f"Invalid content type: {content_type}. URL must point to a web page.")

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'nav', 'footer', 'iframe']):
                element.decompose()
            
            # Try to find main article content
            article_text = ""
            
            # Look for article content in priority order
            content_elements = [
                soup.find('article'),
                soup.find(class_=['article', 'post', 'content', 'entry-content', 'post-content']),
                soup.find(role='main'),
                soup.find('main'),
            ]
            
            content_element = next((el for el in content_elements if el is not None), None)
            
            if content_element:
                # Extract from main content element if found
                paragraphs = content_element.find_all('p')
            else:
                # Fallback to all paragraphs in the body
                body = soup.find('body')
                if not body:
                    raise ValueError("Could not find any content in the webpage")
                paragraphs = body.find_all('p')
            
            # Filter out navigation and footer paragraphs
            for p in paragraphs:
                text = p.get_text().strip()
                # Skip empty paragraphs or those with very short text (likely navigation/buttons)
                if text and len(text) > 10:
                    article_text += text + "\n\n"
            
            if not article_text.strip():
                raise ValueError("Could not extract any meaningful content from the URL")
            
            return article_text.strip()
            
        except requests.exceptions.RequestException as e:
            if 'timeout' in str(e).lower():
                raise ValueError("Request timed out. Please check your internet connection and try again.")
            elif 'certificate' in str(e).lower():
                raise ValueError("SSL certificate verification failed. The website might not be secure.")
            elif '404' in str(e):
                raise ValueError("The page was not found (404 error). Please check if the URL is correct.")
            elif '403' in str(e):
                raise ValueError("Access to this URL is forbidden (403 error). The website might be blocking automated access.")
            else:
                raise ValueError(f"Failed to fetch URL content: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error processing URL: {str(e)}")
    
    def _generate_content(self, source_text: str, word_count: int) -> str:
        """Generate blog content using AI"""
        prompt = f"""
        Based on this source article, create a well-structured blog post.
        Make it engaging and informative, targeting {word_count} words.
        Include proper headings and maintain a professional tone.
        Use clear paragraph separation and proper formatting.
        
        Source content:
        {source_text[:2000]}  # Limit source content to avoid token limits
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional blog writer specializing in AI and technology content. Format your content with clear paragraph separation and proper heading structure."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"Failed to generate content: {str(e)}")
    
    def _generate_meta_info(self, content: str) -> Dict:
        """Generate SEO meta information for the blog post"""
        try:
            meta_prompt = f"""
            Based on this blog post, generate SEO metadata.
            Format your response exactly as:
            Title: [60 chars max]
            Description: [160 chars max]
            Keywords: [comma-separated list]
            
            Blog content:
            {content[:500]}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Generate SEO metadata that is concise and optimized for search engines."},
                    {"role": "user", "content": meta_prompt}
                ]
            )
            
            meta_text = response.choices[0].message.content
            
            # Parse the response
            meta_info = {}
            current_key = None
            
            for line in meta_text.split('\n'):
                line = line.strip()
                if line:
                    if line.startswith('Title:'):
                        current_key = 'title'
                        meta_info[current_key] = line.replace('Title:', '').strip()
                    elif line.startswith('Description:'):
                        current_key = 'description'
                        meta_info[current_key] = line.replace('Description:', '').strip()
                    elif line.startswith('Keywords:'):
                        current_key = 'keywords'
                        meta_info[current_key] = line.replace('Keywords:', '').strip()
                    elif current_key:
                        meta_info[current_key] += ' ' + line
            
            return meta_info
            
        except Exception as e:
            raise Exception(f"Failed to generate meta information: {str(e)}") 