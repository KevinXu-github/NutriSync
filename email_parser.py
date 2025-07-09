import re
from bs4 import BeautifulSoup

def should_process_email(subject, body, sender):
    """Enhanced filtering for DoorDash order confirmations"""
    
    print(f"\n🔍 FILTERING EMAIL...")
    print(f"   Subject: {subject}")
    
    # Must be from DoorDash (direct or forwarded)
    is_doordash = (
        "no-reply@doordash.com" in (sender or "") or
        "doordash.com" in (sender or "") or
        "no-reply@doordash.com" in body or
        "DoorDash Order" in body or
        ("doordash" in body.lower() and "forwarded message" in body.lower())
    )
    
    if not is_doordash:
        print("   ❌ Not from DoorDash")
        return False
    
    # Must have order confirmation indicators
    order_indicators = [
        "Order Confirmation for", "Thanks for your order", "Total Charged",
        "Your receipt", "Track Your Order"
    ]
    
    found_indicators = [ind for ind in order_indicators if ind in body]
    if not found_indicators:
        print("   ❌ No order confirmation indicators")
        return False
    
    # Must have financial indicators
    financial_indicators = ["Total Charged", "Subtotal", "Delivery Fee", "Service Fee", "$"]
    found_financial = [ind for ind in financial_indicators if ind in body]
    if not found_financial:
        print("   ❌ No financial indicators")
        return False
    
    # Exclude non-order emails
    exclusions = [
        "login", "password", "reset", "verification", "promotional", "marketing",
        "survey", "rate your", "we miss you", "special offer", "account", "security"
    ]
    
    combined_text = (body + " " + subject).lower()
    exclusions_found = [exc for exc in exclusions if exc in combined_text]
    if exclusions_found:
        print(f"   ❌ Contains exclusions: {exclusions_found}")
        return False
    
    # Check for restaurant pattern
    restaurant_found = bool(re.search(r"Order Confirmation for .+ from (.+)", body, re.IGNORECASE))
    
    # Final validation - need multiple strong indicators
    strong_indicators = [
        "Order Confirmation" in body,
        "Total Charged" in body,
        "Your receipt" in body,
        "Track Your Order" in body,
        "Delivery Fee" in body or "Service Fee" in body,
        restaurant_found
    ]
    
    strong_count = sum(strong_indicators)
    print(f"   ✓ Strong indicators: {strong_count}/6")
    
    if strong_count >= 3:
        print("   ✅ EMAIL PASSES FILTER")
        return True
    else:
        print(f"   ❌ Not enough indicators ({strong_count}/6)")
        return False

def parse_food_delivery_email(subject, body):
    """Parse food delivery emails"""
    service = detect_service(subject, body)
    
    if service == 'doordash':
        return parse_doordash_email(subject, body)
    elif service == 'ubereats':
        return parse_ubereats_email(subject, body)
    else:
        return None

def detect_service(subject, body):
    """Detect delivery service"""
    text = (subject + " " + body).lower()
    
    if 'doordash' in text:
        return 'doordash'
    elif 'uber eats' in text or 'ubereats' in text:
        return 'ubereats'
    elif 'grubhub' in text:
        return 'grubhub'
    
    return None

def parse_doordash_email(subject, body):
    """Parse DoorDash order confirmation"""
    try:
        soup = BeautifulSoup(body, 'html.parser')
        text_content = soup.get_text() if soup else body
        
        # Extract restaurant - check subject first (best for forwarded emails)
        restaurant = None
        subject_match = re.search(r'Order Confirmation for .+ from (.+)', subject, re.IGNORECASE)
        if subject_match:
            restaurant = subject_match.group(1).strip()
        
        # Fallback to body patterns
        if not restaurant:
            patterns = [
                r'Paid with.*?\n([A-Za-z\s&\']+)\nTotal:',
                r'Paid with.*?([A-Za-z\s&\']+)\s*Total:',
                r'Thanks for your order[^A-Za-z]*([A-Za-z\s&\']+)\n',
                r'order from ([^,\n]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
                if match:
                    candidate = match.group(1).strip()
                    candidate = re.sub(r'Apple Pay|Google Pay|with', '', candidate, flags=re.IGNORECASE).strip()
                    
                    if candidate and len(candidate) > 2 and len(candidate) < 50:
                        restaurant = candidate
                        break
        
        # Extract total
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
        
        # Extract items
        items = []
        item_patterns = [
            r'(\d+)x\s*([^•$\n]+?)(?:•[^$]*?)?\s*\$([0-9]+\.[0-9]{2})',
            r'(\d+)x\s+([^$\n]+?)\s+\$([0-9]+\.[0-9]{2})',
        ]
        
        for pattern in item_patterns:
            matches = re.findall(pattern, text_content, re.MULTILINE)
            for match in matches:
                item_name = match[1].strip()
                item_name = re.sub(r'\s*\([^)]+\)\s*$', '', item_name).strip()
                
                items.append({
                    'quantity': int(match[0]),
                    'name': item_name,
                    'price': float(match[2])
                })
            
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
    """Parse Uber Eats order confirmation"""
    try:
        soup = BeautifulSoup(body, 'html.parser')
        text_content = soup.get_text() if soup else body
        
        # Extract restaurant
        restaurant = None
        patterns = [
            r'Your order from ([^,\n]+)',
            r'Thanks for ordering from ([^,\n]+)',
            r'Receipt for ([^,\n]+)',
        ]
        
        for pattern in patterns:
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
        
        # Extract items
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