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
            
            # Looking at the receipt image, "McDonald's" appears after "Paid with Apple Pay"
            restaurant_patterns = [
                r'Paid with.*?\n([A-Za-z\s&\']+)\nTotal:',  # Based on your receipt format
                r'Your receipt\n.*?\n.*?- For (.+?) -',
                r'order from ([^,\n]+)',
                r'Thanks for your order[^A-Za-z]*([A-Za-z\s&\']+)\n',  # New pattern
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
        
        text_to_search = soup.get_text() if soup else body
        for pattern in total_patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                total = float(match.group(1))
                break
        
        # Extract items with quantities and prices
        items = []
        
        # Pattern for DoorDash items: "1x    Diet Coke® (Beverages)    $1.19"
        item_patterns = [
            r'(\d+)x\s+([^$\n]+?)\s+\$([0-9]+\.[0-9]{2})',
        ]
        
        for pattern in item_patterns:
            matches = re.findall(pattern, text_to_search, re.MULTILINE)
            for match in matches:
                items.append({
                    'quantity': int(match[0]),
                    'name': match[1].strip(),
                    'price': float(match[2])
                })
        
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
    # TODO: Implement Uber Eats parsing
    return {
        'service': 'ubereats',
        'restaurant': 'Unknown Restaurant',
        'total': 0.0,
        'items': []
    }

# Test function with the actual DoorDash email
if __name__ == "__main__":
    # Read the actual DoorDash email content
    with open('paste.txt', 'r', encoding='utf-8') as f:
        email_content = f.read()
    
    # Test subject (simulated)
    test_subject = "Thanks for your order, Kevin"
    
    result = parse_food_delivery_email(test_subject, email_content)
    print("Parsed result:")
    print(f"Service: {result['service']}")
    print(f"Restaurant: {result['restaurant']}")
    print(f"Total: ${result['total']}")
    print(f"Items ({len(result['items'])}):")
    for item in result['items']:
        print(f"  {item['quantity']}x {item['name']} - ${item['price']}")