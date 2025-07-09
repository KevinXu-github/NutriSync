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
        
        # Get text content
        if soup:
            text_content = soup.get_text()
        else:
            text_content = body
            
        # Extract restaurant name - FIXED to remove "Apple Pay" etc
        restaurant = None
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
                
                # Clean up common false matches - FIXED
                restaurant_candidate = restaurant_candidate.replace('Apple Pay', '').strip()
                restaurant_candidate = restaurant_candidate.replace('with', '').strip()
                
                # Validate candidate
                if (restaurant_candidate and 
                    not restaurant_candidate.startswith('Total') and 
                    len(restaurant_candidate) < 50 and
                    len(restaurant_candidate) > 2):
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
                    candidate = match.group(1).strip()
                    candidate = candidate.replace('Apple Pay', '').strip()
                    if candidate:
                        restaurant = candidate
                        break
        
        # Extract total charged
        total = None
        total_patterns = [
            r'Total Charged\s*\$([0-9]+\.[0-9]{2})',
            r'Total:\s*\$([0-9]+\.[0-9]{2})',
        ]
        
        for pattern in total_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                total = float(match.group(1))
                break

        # REMOVED ALL DEBUG OUTPUT - just extract items silently
        items = []
        
        # Pattern for DoorDash items: "1x Diet Coke® (Beverages) • Large (0 Cal.) • No Ice (0 Cal.) $1.19"
        item_patterns = [
            r'(\d+)x\s*([^•$\n]+?)(?:•[^$]*?)?\s*\$([0-9]+\.[0-9]{2})',  # Handle • separators
            r'(\d+)x\s+([^$\n]+?)\s+\$([0-9]+\.[0-9]{2})',  # Original pattern
        ]
        
        for pattern in item_patterns:
            matches = re.findall(pattern, text_content, re.MULTILINE)
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

# COMMENTED OUT - Uncomment to test locally
# if __name__ == "__main__":
#     print("=== TESTING WITH REAL DOORDASH EMAIL ===")
#     
#     try:
#         with open('paste.txt', 'r', encoding='utf-8') as f:
#             email_content = f.read()
#         
#         test_subject = "Thanks for your order, Kevin"
#         result = parse_food_delivery_email(test_subject, email_content)
#         
#         if result:
#             print("✓ Parsing succeeded!")
#             print(f"Service: {result['service']}")
#             print(f"Restaurant: {result['restaurant']}")
#             print(f"Total: ${result['total']}")
#             print(f"Items ({len(result['items'])}):")
#             for item in result['items']:
#                 print(f"  {item['quantity']}x {item['name']} - ${item['price']}")
#         else:
#             print("✗ Parsing failed")
#             
#     except Exception as e:
#         print(f"Error: {e}")