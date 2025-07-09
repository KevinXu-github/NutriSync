import re
from bs4 import BeautifulSoup

def parse_food_delivery_email(subject, body):
    """
    Parse food delivery emails and extract order info
    Returns dict with restaurant, items, total, service
    """
    
    # Determine which service this is from
    service = detect_service(subject, body)
    
    if service == 'doordash':
        return parse_doordash_email(subject, body)
    elif service == 'ubereats':
        return parse_ubereats_email(subject, body)
    else:
        return None

def detect_service(subject, body):
    """Detect which delivery service the email is from"""
    text = (subject + " " + body).lower()
    
    if 'doordash' in text or 'door dash' in text:
        return 'doordash'
    elif 'uber eats' in text or 'ubereats' in text:
        return 'ubereats'
    elif 'grubhub' in text:
        return 'grubhub'
    
    return None

def parse_doordash_email(subject, body):
    """Parse DoorDash order confirmation email"""
    try:
        # Use BeautifulSoup to parse HTML
        soup = BeautifulSoup(body, 'html.parser')
        
        # Extract restaurant name
        restaurant = None
        
        # Try to find restaurant name in various ways
        if soup:
            # Look for text patterns that might contain restaurant name
            text_content = soup.get_text()
        else:
            text_content = body
            
        # Looking at the receipt, "McDonald's" appears after "Paid with Apple Pay"
        restaurant_patterns = [
            r'Paid with.*?\n([A-Za-z\s&\']+)\nTotal:',  # Based on your receipt format
            r'Paid with.*?([A-Za-z\s&\']+)\s*Total:',  # Alternative format
            r'Your receipt\n.*?\n.*?- For (.+?) -',
            r'order from ([^,\n]+)',
            r'Thanks for your order[^A-Za-z]*([A-Za-z\s&\']+)\n',  # New pattern
            r'Paid with [^A-Za-z]*([A-Za-z\s&\']+)(?:\s*Total|\s*\$)',  # More flexible
        ]
        
        for pattern in restaurant_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
            if match:
                restaurant_candidate = match.group(1).strip()
                # Clean up common false matches
                if restaurant_candidate and not restaurant_candidate.startswith('Total') and len(restaurant_candidate) < 50:
                    restaurant = restaurant_candidate
                    break
        
        # If HTML parsing fails, try plain text patterns
        if not restaurant:
            restaurant_patterns = [
                r'Paid with.*?\n([A-Za-z\s&\']+)\n',
                r'order from ([^,\n]+)',
            ]
            for pattern in restaurant_patterns:
                match = re.search(pattern, body, re.IGNORECASE)
                if match:
                    restaurant = match.group(1).strip()
                    break
        
        # Extract total charged
        total = None
        total_patterns = [
            r'Total Charged\s*\$([0-9]+\.[0-9]{2})',
            r'Total:\s*\$([0-9]+\.[0-9]{2})',
        ]
        
        text_to_search = text_content
        for pattern in total_patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                total = float(match.group(1))
                break

        print("\n=== DEBUG: ITEM EXTRACTION ===")
        print("Text content for item search:")
        lines = text_to_search.split('\n')
        for i, line in enumerate(lines):
            if '$' in line and any(char.isdigit() for char in line):
                print(f"Line {i}: {repr(line)}")
        
        print("\nTesting regex patterns:")
        test_patterns = [
            r'(\d+)x\s+([^$\n]+?)\s+\$([0-9]+\.[0-9]{2})',
            r'(\d+)x\s*([^$\n•]+?)(?:\s*•[^$]*?)?\s*\$([0-9]+\.[0-9]{2})',
            r'(\d+)x\s*([^•$\n]+?)(?:•[^$]*?)?\s*\$([0-9]+\.[0-9]{2})',
        ]
        
        for i, pattern in enumerate(test_patterns):
            matches = re.findall(pattern, text_to_search, re.MULTILINE)
            print(f"Pattern {i+1}: Found {len(matches)} matches")
            for match in matches:
                print(f"  {match[0]}x {match[1].strip()} - ${match[2]}")
        print("=== END DEBUG ===\n")
        
        # Extract items with quantities and prices - IMPROVED VERSION
        items = []
        
        # Pattern for DoorDash items: "1x Diet Coke® (Beverages) • Large (0 Cal.) • No Ice (0 Cal.) $1.19"
        item_patterns = [
            r'(\d+)x\s*([^•$\n]+?)(?:•[^$]*?)?\s*\$([0-9]+\.[0-9]{2})',  # Handle • separators
            r'(\d+)x\s+([^$\n]+?)\s+\$([0-9]+\.[0-9]{2})',  # Original pattern
        ]
        
        for pattern in item_patterns:
            matches = re.findall(pattern, text_to_search, re.MULTILINE)
            for match in matches:
                item_name = match[1].strip()
                # Clean up item name (remove extra details after parentheses)
                item_name = re.sub(r'\s*\([^)]+\)\s*$', '', item_name).strip()
                
                items.append({
                    'quantity': int(match[0]),
                    'name': item_name,
                    'price': float(match[2])
                })
            
            # If we found items with this pattern, don't try other patterns
            if items:
                break
        
        return {
            'service': 'doordash',
            'restaurant': restaurant or 'Unknown Restaurant',
            'total': total,
            'items': items
        }
        
    except Exception as e:
        print(f"Error parsing DoorDash email: {e}")
        return None

def parse_ubereats_email(subject, body):
    """Parse Uber Eats order confirmation email"""
    try:
        soup = BeautifulSoup(body, 'html.parser')
        
        # Extract restaurant name
        restaurant = None
        restaurant_patterns = [
            r'Your order from ([^,\n]+)',
            r'Thanks for ordering from ([^,\n]+)',
            r'Receipt for ([^,\n]+)',
        ]
        
        text_content = soup.get_text() if soup else body
        for pattern in restaurant_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                restaurant = match.group(1).strip()
                break
        
        # Extract total
        total = None
        total_patterns = [
            r'Total\s*\$([0-9]+\.[0-9]{2})',
            r'Amount Charged\s*\$([0-9]+\.[0-9]{2})',
            r'Order Total\s*\$([0-9]+\.[0-9]{2})',
        ]
        
        for pattern in total_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                total = float(match.group(1))
                break
        
        # Extract items (Uber Eats format varies)
        items = []
        item_patterns = [
            r'(\d+)\s+x\s+([^$\n]+?)\s+\$([0-9]+\.[0-9]{2})',
            r'(\d+)\s+([^$\n]+?)\s+\$([0-9]+\.[0-9]{2})',
        ]
        
        for pattern in item_patterns:
            matches = re.findall(pattern, text_content, re.MULTILINE)
            for match in matches:
                items.append({
                    'quantity': int(match[0]),
                    'name': match[1].strip(),
                    'price': float(match[2])
                })
        
        return {
            'service': 'ubereats',
            'restaurant': restaurant or 'Unknown Restaurant',
            'total': total,
            'items': items
        }
        
    except Exception as e:
        print(f"Error parsing Uber Eats email: {e}")
        return None

# Test function with the actual DoorDash email
if __name__ == "__main__":
    print("=== TESTING WITH REAL DOORDASH EMAIL ===")
    
    # Try to read your real email
    email_files = ['paste.txt']
    email_content = None
    
    for filename in email_files:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                # Check if this looks like a real email (not a webpage)
                if 'doordash' in content.lower() and len(content) < 50000:  # Reasonable email size
                    email_content = content
                    print(f"✓ Using email from: {filename}")
                    break
                elif 'doordash' in content.lower():
                    email_content = content
                    print(f"✓ Using email from: {filename} (large file, might be webpage)")
                    break
        except FileNotFoundError:
            print(f"File {filename} not found, trying next...")
        except Exception as e:
            print(f"Error reading {filename}: {e}")
    
    if not email_content:
        print("✗ No DoorDash email found!")
        print("Please:")
        print("1. Find a DoorDash email in your Gmail")
        print("2. Copy the entire email content")
        print("3. Save it as 'clean_doordash_email.txt' in this folder")
        exit(1)
    
    print(f"Email content length: {len(email_content)} characters")
    
    # Check if it's HTML or text
    is_html = '<html' in email_content.lower() or '<body' in email_content.lower()
    print(f"Format: {'HTML' if is_html else 'Plain text'}")
    
    # Show a preview of the content
    print("\n=== EMAIL CONTENT PREVIEW ===")
    if is_html:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(email_content, 'html.parser')
        text_preview = soup.get_text()[:300].strip()
        print(f"Text preview: {repr(text_preview)}")
    else:
        print(f"Content preview: {repr(email_content[:300])}")
    
    # Test with a realistic subject
    test_subject = "Thanks for your order, Kevin"
    print(f"\n✓ Using test subject: '{test_subject}'")
    
    # Test service detection
    print("\n=== SERVICE DETECTION ===")
    detected_service = detect_service(test_subject, email_content)
    print(f"Detected service: {detected_service}")
    
    # Check for DoorDash keywords manually
    combined_text = (test_subject + " " + email_content).lower()
    doordash_keywords = ['doordash', 'door dash']
    found_keywords = [kw for kw in doordash_keywords if kw in combined_text]
    print(f"Found keywords: {found_keywords}")
    
    if detected_service != 'doordash':
        print("✗ Service detection failed!")
        if found_keywords:
            print("But keywords were found - there might be an issue with the detect_service function")
        exit(1)
    
    # Test full parsing
    print("\n=== FULL PARSING ===")
    result = parse_food_delivery_email(test_subject, email_content)
    
    if result is None:
        print("✗ Full parsing returned None")
        # Test DoorDash parsing directly
        print("\n=== TESTING DOORDASH PARSER DIRECTLY ===")
        doordash_result = parse_doordash_email(test_subject, email_content)
        if doordash_result:
            print("✓ Direct DoorDash parsing worked!")
            print(f"Restaurant: {doordash_result.get('restaurant')}")
            print(f"Total: ${doordash_result.get('total')}")
            print(f"Items: {len(doordash_result.get('items', []))}")
        else:
            print("✗ Direct DoorDash parsing also failed")
    else:
        print("✓ Parsing succeeded!")
        print(f"Service: {result['service']}")
        print(f"Restaurant: {result['restaurant']}")
        print(f"Total: ${result['total']}")
        print(f"Items ({len(result['items'])}):")
        for item in result['items']:
            print(f"  {item['quantity']}x {item['name']} - ${item['price']}")