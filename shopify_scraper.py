#!/usr/bin/env python3
"""
Shopify Product Scraper
Scrapes product data from Shopify sites via sitemap.xml and outputs in schema.org format
"""

import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import json
import re
import time
import logging
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any, Optional
import openai
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ShopifyScraper:
    def __init__(self, max_workers: int = 8):
        """Initialize the scraper with parallel processing settings."""
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(
            api_key=os.getenv('OPENAI_API_KEY') or input("Please enter your OpenAI API key: ")
        )
        
        # Store all products
        self.products = []
        self.lock = threading.Lock()
        
    def get_sitemap_urls(self, base_url: str) -> List[str]:
        """Extract all sitemap URLs from the main sitemap.xml."""
        try:
            # Ensure base_url ends with /
            if not base_url.endswith('/'):
                base_url += '/'
            
            sitemap_url = urljoin(base_url, 'sitemap.xml')
            logger.info(f"Fetching sitemap from: {sitemap_url}")
            
            response = self.session.get(sitemap_url, timeout=30)
            response.raise_for_status()
            
            # Parse XML using built-in parser
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as e:
                logger.error(f"Failed to parse sitemap XML: {e}")
                return []
            
            # Extract sitemap URLs - handle different namespace formats
            sitemap_urls = []
            
            # Try different namespace patterns
            namespaces = [
                '{http://www.sitemaps.org/schemas/sitemap/0.9}',
                '',
                '{http://www.google.com/schemas/sitemap/0.84}'
            ]
            
            for namespace in namespaces:
                sitemap_elements = root.findall(f'.//{namespace}sitemap')
                if sitemap_elements:
                    for sitemap in sitemap_elements:
                        loc = sitemap.find(f'{namespace}loc')
                        if loc is not None and loc.text:
                            sitemap_urls.append(loc.text)
                    break
            
            logger.info(f"Found {len(sitemap_urls)} sitemap URLs")
            return sitemap_urls
            
        except Exception as e:
            logger.error(f"Error fetching sitemap: {e}")
            return []
    
    def get_product_urls_from_sitemap(self, sitemap_url: str) -> List[str]:
        """Extract product URLs from a sitemap."""
        try:
            logger.info(f"Fetching product URLs from: {sitemap_url}")
            response = self.session.get(sitemap_url, timeout=30)
            response.raise_for_status()
            
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as e:
                logger.error(f"Failed to parse sitemap XML: {e}")
                return []
            
            # Extract URLs - handle different namespace formats
            product_urls = []
            namespaces = [
                '{http://www.sitemaps.org/schemas/sitemap/0.9}',
                '',
                '{http://www.google.com/schemas/sitemap/0.84}'
            ]
            
            for namespace in namespaces:
                url_elements = root.findall(f'.//{namespace}url')
                if url_elements:
                    for url_elem in url_elements:
                        loc = url_elem.find(f'{namespace}loc')
                        if loc is not None and loc.text:
                            url_text = loc.text
                            # Filter for product URLs (common patterns)
                            if any(pattern in url_text.lower() for pattern in ['/products/', '/product/']):
                                product_urls.append(url_text)
                    break
            
            logger.info(f"Found {len(product_urls)} product URLs in {sitemap_url}")
            return product_urls
            
        except Exception as e:
            logger.error(f"Error fetching product URLs from {sitemap_url}: {e}")
            return []
    
    def extract_product_data_with_gpt(self, html_content: str, url: str) -> Optional[Dict[str, Any]]:
        """Use ChatGPT to extract structured product data from HTML, including variants."""
        try:
            # Prepare the prompt for GPT with enhanced data extraction
            prompt = f"""
            Extract comprehensive product information from this Shopify product page HTML. Return ONLY a JSON object with these exact fields:
            - id: Numeric product ID (internal Shopify ID)
            - gid: Global ID (gid://shopify/Product/...)
            - vendor: Brand or manufacturer (should be "Down to Earth Project LLC" for this store)
            - type: Product category/type
            - price: Price in cents (e.g., 15000 = $150.00)
            - name: Full product name with variant description
            - description: Full product description text
            - availability: Availability status (in stock, out of stock, pre-order, etc.)
            - tags: Array of product tags/categories
            - images: Array of image URLs (main product images)
            - weight: Product weight if available
            - dimensions: Product dimensions if available
            - tax_info: Tax/VAT information if available
            - reviews: Array of review objects with rating and text if available
            - variants: Array of variant objects, each with:
                - id: Variant ID (look for data-variant-id, variant_id, or similar attributes)
                - name: Variant name (e.g., "L / Black", "Medium / Blue", etc.)
                - sku: Stock Keeping Unit
                - price: Price in cents
                - availability: Availability status
                - image: Image URL for the variant if available
                - options: Object with size, color, etc. (e.g., {{"size": "L", "color": "Black"}})
            
            IMPORTANT: Look carefully for variant information in:
            - <select> elements with size/color options
            - data attributes like data-variant-id, data-option-value
            - JSON-LD structured data
            - JavaScript variables containing variant data
            - Form elements with variant selections
            
            If any field is not found, use null. For arrays, use empty array if none found.
            Return ONLY the JSON object, no other text.
            
            HTML Content:
            {html_content[:12000]}  # Increased content limit for more data
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a data extraction expert. Extract comprehensive product information and return only valid JSON. Pay special attention to finding ALL product variants, their sizes, colors, prices, and IDs. Look for variant data in select elements, data attributes, JSON-LD, and JavaScript variables."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,  # Increased token limit for more data
                temperature=0
            )
            
            # Extract JSON from response
            content = response.choices[0].message.content.strip()
            
            # Try to find JSON in the response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                product_data = json.loads(json_match.group())
                product_data['url'] = url
                
                # Apply fallback fixes for common issues, including variants
                product_data = self._apply_fallback_fixes(product_data, html_content, url)
                
                return product_data
            else:
                logger.warning(f"Could not extract JSON from GPT response for {url}")
                # Try fallback extraction
                return self._fallback_extraction(html_content, url)
                
        except Exception as e:
            logger.error(f"Error extracting product data with GPT for {url}: {e}")
            # Try fallback extraction
            return self._fallback_extraction(html_content, url)
    
    def _apply_fallback_fixes(self, product_data: Dict[str, Any], html_content: str, url: str) -> Dict[str, Any]:
        """Apply fallback fixes for common extraction issues, including variants."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Fix vendor if null
        if not product_data.get('vendor'):
            product_data['vendor'] = "Down to Earth Project LLC"
        
        # Try to extract product ID from various sources
        if not product_data.get('id') or product_data.get('id') == 'None':
            # Look for product ID in various attributes
            product_id = None
            for selector in [
                '[data-product-id]',
                '[data-product-id]',
                '.product-single__meta [data-product-id]',
                'script[type="application/ld+json"]'
            ]:
                elements = soup.select(selector)
                for element in elements:
                    if element.get('data-product-id'):
                        product_id = element.get('data-product-id')
                        break
                    elif element.string and '"@type":"Product"' in element.string:
                        # Try to extract from JSON-LD
                        try:
                            json_data = json.loads(element.string)
                            if isinstance(json_data, dict) and json_data.get('@type') == 'Product':
                                if json_data.get('@id'):
                                    product_id = json_data['@id'].split('/')[-1]
                                    break
                        except:
                            pass
            
            if product_id:
                product_data['id'] = product_id
                product_data['gid'] = f"gid://shopify/Product/{product_id}"
        
        # Try to extract price if missing or wrong
        if not product_data.get('price') or product_data.get('price') == 0:
            price_selectors = [
                '.price__regular .price-item--regular',
                '.product__price .price-item--regular',
                '[data-price]',
                '.price'
            ]
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text().strip()
                    price_match = re.search(r'\$?(\d+\.?\d*)', price_text)
                    if price_match:
                        price = float(price_match.group(1))
                        product_data['price'] = int(price * 100)  # Convert to cents
                        break
        
        # Try to extract images if missing
        if not product_data.get('images') or not isinstance(product_data.get('images'), list):
            images = []
            img_selectors = [
                '.product__media img',
                '.product-single__photo img',
                '.product__image img',
                'img[data-src]',
                'img[src*="cdn.shopify.com"]'
            ]
            for selector in img_selectors:
                img_elements = soup.select(selector)
                for img in img_elements:
                    src = img.get('src') or img.get('data-src')
                    if src and 'cdn.shopify.com' in src:
                        if not src.startswith('http'):
                            src = 'https:' + src if src.startswith('//') else 'https://' + src
                        images.append(src)
                if images:
                    break
            product_data['images'] = images
        
        # Try to extract description if missing
        if not product_data.get('description'):
            desc_selectors = [
                '.product__description',
                '.product-single__description',
                '[data-product-description]',
                '.rte'
            ]
            for selector in desc_selectors:
                desc_elem = soup.select_one(selector)
                if desc_elem:
                    product_data['description'] = desc_elem.get_text().strip()
                    break
        
        # Fallback for variants if missing or empty
        if not product_data.get('variants') or not isinstance(product_data.get('variants'), list) or not product_data['variants']:
            product_data['variants'] = self._extract_variants_from_html(soup)
        
        return product_data
    
    def _extract_variants_from_html(self, soup: BeautifulSoup) -> list:
        """Return an empty list for variants (temporarily disabled extraction)."""
        return []
    
    def _fallback_extraction(self, html_content: str, url: str) -> Optional[Dict[str, Any]]:
        """Fallback extraction method when GPT fails."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract basic product info
            product_data = {
                'url': url,
                'vendor': 'Down to Earth Project LLC',
                'name': '',
                'price': 0,
                'id': None,
                'gid': None,
                'description': '',
                'images': [],
                'availability': 'in stock',
                'tags': [],
                'type': None,
                'sku': None,
                'variant_id': None,
                'public_title': None,
                'weight': None,
                'dimensions': None,
                'tax_info': None,
                'reviews': [],
                'variants': []
            }
            
            # Extract product name
            name_selectors = [
                'h1.product-single__title',
                '.product__title h1',
                'h1[data-product-title]',
                'h1'
            ]
            for selector in name_selectors:
                name_elem = soup.select_one(selector)
                if name_elem:
                    product_data['name'] = name_elem.get_text().strip()
                    break
            
            # Extract price
            price_selectors = [
                '.price__regular .price-item--regular',
                '.product__price .price-item--regular',
                '[data-price]',
                '.price'
            ]
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text().strip()
                    price_match = re.search(r'\$?(\d+\.?\d*)', price_text)
                    if price_match:
                        price = float(price_match.group(1))
                        product_data['price'] = int(price * 100)
                        break
            
            # Extract images
            img_selectors = [
                '.product__media img',
                '.product-single__photo img',
                '.product__image img',
                'img[data-src]',
                'img[src*="cdn.shopify.com"]'
            ]
            for selector in img_selectors:
                img_elements = soup.select(selector)
                for img in img_elements:
                    src = img.get('src') or img.get('data-src')
                    if src and 'cdn.shopify.com' in src:
                        if not src.startswith('http'):
                            src = 'https:' + src if src.startswith('//') else 'https://' + src
                        product_data['images'].append(src)
                if product_data['images']:
                    break
            
            # Extract description
            desc_selectors = [
                '.product__description',
                '.product-single__description',
                '[data-product-description]',
                '.rte'
            ]
            for selector in desc_selectors:
                desc_elem = soup.select_one(selector)
                if desc_elem:
                    product_data['description'] = desc_elem.get_text().strip()
                    break
            
            # Try to extract product ID from URL
            url_match = re.search(r'/products/([^/?]+)', url)
            if url_match:
                product_data['id'] = url_match.group(1)
                product_data['gid'] = f"gid://shopify/Product/{product_data['id']}"
            
            # Extract variants
            product_data['variants'] = self._extract_variants_from_html(soup)
            
            return product_data
            
        except Exception as e:
            logger.error(f"Fallback extraction failed for {url}: {e}")
            return None
    
    def scrape_product_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape a single product page and extract data."""
        try:
            logger.info(f"Scraping product page: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Extract product data using GPT
            product_data = self.extract_product_data_with_gpt(response.text, url)
            
            if product_data:
                logger.info(f"Successfully extracted data for product: {product_data.get('name', 'Unknown')}")
                return product_data
            else:
                logger.warning(f"Failed to extract product data from {url}")
                return None
                
        except Exception as e:
            logger.error(f"Error scraping product page {url}: {e}")
            return None
    
    def scrape_product_parallel(self, url: str) -> Optional[Dict[str, Any]]:
        """Wrapper for parallel scraping with thread safety."""
        product_data = self.scrape_product_page(url)
        if product_data:
            with self.lock:
                self.products.append(product_data)
        return product_data
    
    def scrape_all_products(self, base_url: str) -> List[Dict[str, Any]]:
        """Main method to scrape all products from a Shopify site with parallel processing."""
        logger.info(f"Starting scrape for: {base_url}")
        
        # Get all sitemap URLs
        sitemap_urls = self.get_sitemap_urls(base_url)
        
        if not sitemap_urls:
            logger.warning("No sitemap URLs found, trying direct sitemap.xml")
            sitemap_urls = [urljoin(base_url, 'sitemap.xml')]
        
        # Get product URLs from all sitemaps
        all_product_urls = []
        for sitemap_url in sitemap_urls:
            product_urls = self.get_product_urls_from_sitemap(sitemap_url)
            all_product_urls.extend(product_urls)
        
        # Remove duplicates
        all_product_urls = list(set(all_product_urls))
        logger.info(f"Total unique product URLs found: {len(all_product_urls)}")
        
        # Scrape products in parallel
        products = []
        completed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all scraping tasks
            future_to_url = {executor.submit(self.scrape_product_parallel, url): url for url in all_product_urls}
            
            # Process completed tasks
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                completed += 1
                logger.info(f"Completed {completed}/{len(all_product_urls)} products")
                
                try:
                    product_data = future.result()
                    if product_data:
                        products.append(product_data)
                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                
                # Add small delay to be respectful
                time.sleep(0.2)
        
        self.products = products
        logger.info(f"Successfully scraped {len(products)} products")
        return products
    
    def generate_schema_org_output(self) -> str:
        """Generate schema.org formatted output with enhanced data and variants, plus schema comment and documentation."""
        # --- SCHEMA COMMENT AND DOCUMENTATION ---
        schema_comment = """/*
Purpose: This file contains a normalized, AI-friendly list of Shopify products and their variants scraped from a store.
It is designed to make it easy for an AI agent to search, filter, and select products and variants for purchase,
without needing to scrape the site again.

Schema Template:
{
  'products': [
    {
      'product_id': str, // Unique Shopify product ID
      'name': str, // Product name
      'description': str, // Product description
      'brand': str, // Brand or vendor
      'category': str, // Product category/type
      'tags': [str], // List of tags/keywords
      'url': str, // Product page URL
      'image_urls': [str], // List of product image URLs
      'price_cents': int, // Default price in cents
      'availability': str, // Product-level availability
      'variants': [
        {
          'variant_id': str, // Unique variant ID
          'name': str, // Variant name (e.g., 'L / Black')
          'sku': str, // SKU
          'price_cents': int, // Price in cents
          'availability': str, // Variant-level availability
          'image_url': str, // Variant image URL
          'options': {str: str} // Option name-value pairs (e.g., {'size': 'L', 'color': 'Black'})
        }
      ]
    }
  ]
}

Field Explanations:
- product_id: Unique Shopify product ID (string or number as string)
- name: Product name
- description: Full product description
- brand: Brand or vendor name
- category: Product category/type (if available)
- tags: List of tags/keywords (if available)
- url: Product page URL
- image_urls: List of product image URLs
- price_cents: Default product price in cents (integer)
- availability: Product-level availability (e.g., 'InStock', 'OutOfStock')
- variants: List of variant objects, each with:
    - variant_id: Unique variant ID
    - name: Variant name (e.g., 'L / Black')
    - sku: Stock Keeping Unit
    - price_cents: Price in cents (integer)
    - availability: Variant-level availability
    - image_url: Variant image URL
    - options: Dictionary of option name-value pairs (e.g., {'size': 'L', 'color': 'Black'})
*/
"""
        # --- END SCHEMA COMMENT ---

        # --- NORMALIZED DATA ---
        products = []
        for product in self.products:
            # Normalize product fields
            normalized = {
                'product_id': str(product.get('id', '')),
                'name': product.get('name', '') or '',
                'description': product.get('description', '') or '',
                'brand': product.get('vendor', '') or '',
                'category': product.get('type', '') or '',
                'tags': product.get('tags', []) if isinstance(product.get('tags'), list) else [],
                'url': product.get('url', '') or '',
                'image_urls': product.get('images', []) if isinstance(product.get('images'), list) else [],
                'price_cents': int(product.get('price', 0)) if product.get('price') else 0,
                'availability': self._map_availability(product.get('availability', '')),
                'variants': []
            }
            # Normalize variants
            for variant in product.get('variants', []):
                normalized_variant = {
                    'variant_id': str(variant.get('id', '')),
                    'name': variant.get('name', '') or '',
                    'sku': variant.get('sku', '') or '',
                    'price_cents': int(variant.get('price', 0)) if variant.get('price') else 0,
                    'availability': self._map_availability(variant.get('availability', '')),
                    'image_url': variant.get('image', '') or '',
                    'options': variant.get('options', {}) if isinstance(variant.get('options', {}), dict) else {}
                }
                normalized['variants'].append(normalized_variant)
            products.append(normalized)
        # --- OUTPUT ---
        output = schema_comment + json.dumps({'products': products}, indent=2, ensure_ascii=False)
        return output
    
    def _map_availability(self, availability: str) -> str:
        """Map availability text to schema.org format."""
        if not availability:
            return "https://schema.org/InStock"  # Default for None/empty
            
        availability_lower = availability.lower()
        if 'in stock' in availability_lower or 'available' in availability_lower:
            return "https://schema.org/InStock"
        elif 'out of stock' in availability_lower or 'unavailable' in availability_lower:
            return "https://schema.org/OutOfStock"
        elif 'pre-order' in availability_lower or 'preorder' in availability_lower:
            return "https://schema.org/PreOrder"
        else:
            return "https://schema.org/InStock"  # Default
    
    def save_to_file(self, filename: str = "slashask.txt"):
        """Save the schema.org output to a file."""
        try:
            schema_output = self.generate_schema_org_output()
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(schema_output)
            logger.info(f"Output saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving to file: {e}")

def main():
    """Main function to run the scraper."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape Shopify products from a store URL')
    parser.add_argument('base_url', help='Base URL of the Shopify store')
    parser.add_argument('--threads', type=int, default=8, help='Number of parallel threads (default: 8)')
    
    args = parser.parse_args()
    
    base_url = args.base_url
    
    # Initialize scraper with parallel processing
    scraper = ShopifyScraper(max_workers=args.threads)
    
    # Scrape all products
    products = scraper.scrape_all_products(base_url)
    
    # Save output
    scraper.save_to_file()
    
    print(f"\nScraping completed! Found {len(products)} products.")
    print("Output saved to slashask.txt")

if __name__ == "__main__":
    main() 