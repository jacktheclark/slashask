# Shopify Product Scraper

This tool scrapes Shopify product data from a given store's sitemap.xml and sub-sitemaps, extracting detailed product information including IDs, vendor, type, prices, names, SKUs, and outputs the data in schema.org format to a file named `slashask.txt`.

## Features
- Extracts product IDs, vendor, type, price, name, SKU, images, description, availability, tags, and more
- Outputs normalized, AI-friendly schema.org JSON to `slashask.txt`
- **Variants extraction is currently disabled** (the `variants` field will be blank for all products)
- Parallel scraping for speed (configurable number of threads)

## Usage

```bash
python ask.py <shopify_store_url> [--threads N]
```
- `<shopify_store_url>`: The base URL of the Shopify store (e.g., `https://examplestore.com/`)
- `--threads N`: (Optional) Number of parallel threads to use for scraping (default: 8)

Example:
```bash
python ask.py https://downtoearthprojllc.com/ --threads 12
```

## Output
- The output file `slashask.txt` contains a JSON object with a `products` array, each with normalized fields for easy AI search.
- The `variants` field is currently always an empty list.

## Performance Tips
- Increase the `--threads` value for faster scraping, but be mindful of server rate limits.
- Use a fast, stable internet connection.
- Avoid running multiple scrapes in parallel to the same store to prevent being blocked.

## Requirements
- Python 3.8+
- `requests`, `beautifulsoup4`, `openai` (for GPT fallback)
- OpenAI API key (set via `OPENAI_API_KEY` environment variable or entered when prompted)

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set your OpenAI API key (optional - you'll be prompted if not set):
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

## Notes
- This tool is optimized for Shopify stores with standard sitemaps and product pages.
- If you need variant extraction, contact the maintainer or check for future updates.

## Installation

1. **Clone or download this repository**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation**:
   ```bash
   python ask.py --help
   ```

## Output Format

The tool generates a `slashask.txt` file containing schema.org formatted JSON with the following structure:

```json
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "itemListElement": [
    {
      "@type": "Product",
      "position": 1,
      "item": {
        "@type": "Product",
        "name": "Product Name",
        "brand": {
          "@type": "Brand",
          "name": "Vendor Name"
        },
        "category": "Product Type",
        "sku": "SKU123",
        "mpn": "12345",
        "identifier": "gid://shopify/Product/12345",
        "offers": {
          "@type": "Offer",
          "price": "150.00",
          "priceCurrency": "USD",
          "availability": "https://schema.org/InStock"
        },
        "additionalProperty": [
          {
            "@type": "PropertyValue",
            "name": "variant_id",
            "value": "67890"
          },
          {
            "@type": "PropertyValue",
            "name": "variant_title",
            "value": "METEORITE BLACK / L"
          }
        ]
      }
    }
  ]
}
```

## Error Handling

The tool includes comprehensive error handling:
- Network timeouts and connection errors
- Invalid XML/HTML content
- Missing or malformed data
- Rate limiting considerations

## Rate Limiting

The tool includes a 1-second delay between product page requests to be respectful to the target website.

## Troubleshooting

### Common Issues

1. **"No sitemap URLs found"**: The website might not have a standard sitemap.xml structure
2. **"Failed to extract product data"**: The product page might have a non-standard structure
3. **Network timeouts**: The website might be slow or blocking requests

### Solutions

- Ensure the base URL is correct and accessible
- Check if the website has a robots.txt file that might block scraping
- Verify the website is a Shopify store
- Try running the tool during off-peak hours

## License

This tool is provided as-is for educational and research purposes. Please ensure you comply with the target website's terms of service and robots.txt file.

## Support

For issues or questions, please check the error logs that are displayed during execution. The tool provides detailed logging to help diagnose any problems. 