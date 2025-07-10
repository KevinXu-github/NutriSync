from flask import Flask, request, jsonify
import json
import hashlib
import hmac
import re
from datetime import datetime

app = Flask(__name__)

# Your Mailgun webhook signing key
WEBHOOK_SIGNING_KEY = "53929c56588d06f7b5c12856406207e0"

def verify_webhook_signature(token, timestamp, signature):
    """Verify that the webhook is from Mailgun"""
    try:
        hmac_digest = hmac.new(
            key=WEBHOOK_SIGNING_KEY.encode('utf-8'),
            msg='{}{}'.format(timestamp, token).encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, hmac_digest)
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False

def extract_verification_link(body):
    """Extract Gmail verification link from email body"""
    
    # Convert HTML to text if needed
    from bs4 import BeautifulSoup
    if '<html' in body.lower():
        soup = BeautifulSoup(body, 'html.parser')
        text_body = soup.get_text()
    else:
        text_body = body
    
    # Look for Gmail verification URLs
    patterns = [
        r'https://accounts\.google\.com/[^\s<>"\']+',
        r'https://mail\.google\.com/[^\s<>"\']+',
        r'https://[^\s<>"\']*gmail[^\s<>"\']*verify[^\s<>"\']*',
        r'https://[^\s<>"\']*google[^\s<>"\']*confirm[^\s<>"\']*',
        r'https://[^\s<>"\']*forwarding[^\s<>"\']*',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text_body, re.IGNORECASE)
        if matches:
            # Return the first match, cleaned up
            link = matches[0].rstrip('.,;!?')
            return link
    
    # Also check in the original HTML for href attributes
    if '<html' in body.lower():
        href_pattern = r'href=["\']([^"\']*(?:verify|confirm|forwarding)[^"\']*)["\']'
        href_matches = re.findall(href_pattern, body, re.IGNORECASE)
        if href_matches:
            return href_matches[0]
    
    return None

@app.route('/')
def hello():
    return """
    <h1>🍔 NutriSync - DoorDash Order Parser with USDA Macro Tracking</h1>
    <h2>📧 Gmail Verification Helper</h2>
    <p>When you set up Gmail forwarding, check your console logs for the verification link!</p>
    <p>Recent verification links are also saved to <code>gmail_verification_*.txt</code> files.</p>
    
    <h2>🍎 USDA Nutrition Features</h2>
    <p><strong>NEW:</strong> Now uses USDA FoodData Central API for real nutrition data!</p>
    <ul>
        <li>✅ Real-time nutrition lookup via USDA API</li>
        <li>✅ Smart food matching (tries multiple search strategies)</li>
        <li>✅ Caching to avoid repeated API calls</li>
        <li>✅ Enhanced orders saved as <code>enhanced_order_*.json</code></li>
    </ul>
    
    <h2>🔗 Useful Endpoints</h2>
    <ul>
        <li><a href="/verification-files">/verification-files</a> - View Gmail verification links</li>
        <li><a href="/nutrition-summary">/nutrition-summary</a> - View recent nutrition summary</li>
        <li><a href="/test">/test</a> - Test with local paste.txt file</li>
    </ul>
    """

@app.route('/webhook/email', methods=['POST'])
def handle_email():
    """Process incoming emails with enhanced Gmail verification handling and USDA nutrition tracking"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n📧 WEBHOOK RECEIVED - {timestamp}")
    
    try:
        # Get email data (handle both JSON and form data)
        email_data = request.get_json() if request.is_json else dict(request.form)
        
        # Verify webhook signature (optional but recommended)
        webhook_signature = email_data.get('signature')
        webhook_timestamp = email_data.get('timestamp')
        webhook_token = email_data.get('token')
        
        if webhook_signature and webhook_timestamp and webhook_token:
            if not verify_webhook_signature(webhook_token, webhook_timestamp, webhook_signature):
                print("❌ Invalid webhook signature")
                return jsonify({"status": "error", "message": "Invalid signature"}), 403
        
        # Extract email details
        subject = email_data.get('subject', '')
        sender = email_data.get('sender', '') or email_data.get('from', '')
        body = (email_data.get('stripped-html') or 
                email_data.get('body-html') or 
                email_data.get('stripped-text') or
                email_data.get('body-plain', ''))
        
        print(f"From: {sender}")
        print(f"Subject: {subject}")
        print(f"Body length: {len(body)}")
        
        # Handle Gmail verification emails with link extraction
        if 'forwarding-noreply@google.com' in sender:
            print("✅ Gmail verification email received")
            
            # Extract verification link from email body
            verification_link = extract_verification_link(body)
            
            if verification_link:
                print(f"\n🔗 VERIFICATION LINK FOUND:")
                print(f"🔗 {verification_link}")
                print(f"🔗 Copy and paste this link in your browser to verify Gmail forwarding!")
                
                # Save verification link to file for easy access
                verification_file = f"gmail_verification_{timestamp}.txt"
                with open(verification_file, 'w') as f:
                    f.write(f"Gmail Verification Link:\n")
                    f.write(f"{verification_link}\n\n")
                    f.write(f"Instructions:\n")
                    f.write(f"1. Copy the link above\n")
                    f.write(f"2. Paste it in your browser\n")
                    f.write(f"3. Click to verify Gmail forwarding\n")
                    f.write(f"4. Return to Gmail settings to confirm verification\n")
                
                print(f"📄 Verification link saved to: {verification_file}")
                
                # Also save the full email for debugging
                with open(f"gmail_verification_full_{timestamp}.txt", 'w') as f:
                    f.write(f"Subject: {subject}\n")
                    f.write(f"From: {sender}\n")
                    f.write(f"Body:\n{body}\n")
                
                return jsonify({
                    "status": "success", 
                    "message": "Gmail verification handled",
                    "verification_link": verification_link,
                    "instructions": "Copy the verification_link and paste it in your browser to complete Gmail forwarding setup"
                }), 200
            else:
                print("⚠️ No verification link found in email")
                # Still save the email for manual inspection
                with open(f"gmail_verification_no_link_{timestamp}.txt", 'w') as f:
                    f.write(f"Subject: {subject}\n")
                    f.write(f"From: {sender}\n")
                    f.write(f"Body:\n{body}\n")
                
                return jsonify({
                    "status": "success", 
                    "message": "Gmail verification received but no link found",
                    "note": "Check the saved email file for manual verification"
                }), 200
        
        # Handle other system emails
        if any(skip in sender.lower() for skip in ['noreply', 'no-reply', 'system', 'admin']):
            if 'doordash' not in sender.lower() and 'doordash' not in subject.lower():
                print("⏭️ System email - ignoring")
                return jsonify({"status": "ignored", "reason": "System email"}), 200
        
        # Process DoorDash emails
        from email_parser import should_process_email, parse_food_delivery_email
        
        if not should_process_email(subject, body, sender):
            print("⏭️ Email filtered out")
            return jsonify({"status": "filtered", "reason": "Not a DoorDash order"}), 200
        
        # Parse order
        result = parse_food_delivery_email(subject, body)
        
        if result:
            print(f"\n✅ ORDER PARSED!")
            print(f"🏪 Restaurant: {result['restaurant']}")
            print(f"💰 Total: ${result['total']}")
            print(f"🍔 Items ({len(result['items'])}):")
            
            for i, item in enumerate(result['items']):
                print(f"   {i+1}. {item['quantity']}x {item['name']} - ${item['price']}")
            
            # Save original order
            order_file = f"order_{timestamp}.json"
            with open(order_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"📄 Order saved to: {order_file}")
            
            # NEW: Add USDA nutrition analysis
            try:
                print(f"\n🔄 STARTING USDA NUTRITION LOOKUP...")
                from nutrition_tracker import enhance_order_with_nutrition
                enhanced_order = enhance_order_with_nutrition(result)
                
                # Save enhanced order with nutrition data
                enhanced_file = f"enhanced_order_{timestamp}.json"
                with open(enhanced_file, 'w') as f:
                    json.dump(enhanced_order, f, indent=2)
                
                print(f"🍎 Enhanced order with USDA nutrition saved to: {enhanced_file}")
                
                # Count successful nutrition lookups
                items_with_nutrition = sum(1 for item in enhanced_order['items'] if item.get('nutrition'))
                total_items = len(enhanced_order['items'])
                
                # Return enhanced response
                return jsonify({
                    "status": "success",
                    "restaurant": result['restaurant'],
                    "total": result['total'],
                    "items_count": total_items,
                    "nutrition_found": f"{items_with_nutrition}/{total_items}",
                    "total_calories": enhanced_order['meal_totals']['total_calories'],
                    "macro_breakdown": enhanced_order['meal_totals']['macro_percentages'],
                    "timestamp": timestamp,
                    "order_file": order_file,
                    "enhanced_file": enhanced_file,
                    "nutrition_source": "USDA FoodData Central API"
                }), 200
                
            except Exception as nutrition_error:
                print(f"⚠️ USDA nutrition analysis failed: {nutrition_error}")
                print("📄 Continuing with basic order data...")
                import traceback
                traceback.print_exc()
                
                # Fall back to original behavior if nutrition fails
                return jsonify({
                    "status": "partial_success",
                    "restaurant": result['restaurant'],
                    "total": result['total'],
                    "items_count": len(result['items']),
                    "nutrition_error": str(nutrition_error),
                    "timestamp": timestamp,
                    "order_file": order_file,
                    "note": "Order parsed successfully but nutrition lookup failed"
                }), 200
            
        else:
            print("❌ Parsing failed")
            return jsonify({"status": "failed", "reason": "Parsing failed"}), 200
            
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 200  # Return 200 to avoid retries

@app.route('/test')
def test():
    """Test with local file using USDA nutrition lookup"""
    try:
        with open('paste.txt', 'r', encoding='utf-8') as f:
            body = f.read()
        
        subject = "Fwd: Order Confirmation for Kevin from McDonald's"
        sender = "xuk654@gmail.com"
        
        from email_parser import should_process_email, parse_food_delivery_email
        
        print(f"\n🧪 LOCAL TEST - {subject}")
        print(f"🔑 Testing USDA API nutrition lookup...")
        
        if should_process_email(subject, body, sender):
            result = parse_food_delivery_email(subject, body)
            if result:
                # Test USDA nutrition analysis
                try:
                    from nutrition_tracker import enhance_order_with_nutrition
                    enhanced_order = enhance_order_with_nutrition(result)
                    
                    # Count successful lookups
                    items_with_nutrition = sum(1 for item in enhanced_order['items'] if item.get('nutrition'))
                    total_items = len(enhanced_order['items'])
                    
                    return jsonify({
                        "status": "success",
                        "restaurant": result['restaurant'],
                        "total": result['total'],
                        "items": enhanced_order['items'],
                        "nutrition_analysis": enhanced_order['meal_totals'],
                        "nutrition_found": f"{items_with_nutrition}/{total_items} items",
                        "test_note": "Using USDA FoodData Central API for real nutrition data"
                    })
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    return jsonify({
                        "status": "partial_success",
                        "restaurant": result['restaurant'],
                        "total": result['total'],
                        "items": result['items'],
                        "nutrition_error": str(e),
                        "note": "Order parsed but USDA nutrition lookup failed"
                    })
            else:
                return jsonify({"status": "failed", "message": "Parsing failed"})
        else:
            return jsonify({"status": "filtered", "message": "Email filtered out"})
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/verification-files')
def list_verification_files():
    """List all verification files for easy access"""
    import os
    import glob
    
    verification_files = glob.glob("gmail_verification_*.txt")
    
    if not verification_files:
        return jsonify({"message": "No verification files found"})
    
    files_info = []
    for file in sorted(verification_files, reverse=True):  # Most recent first
        try:
            with open(file, 'r') as f:
                content = f.read()
                files_info.append({
                    "filename": file,
                    "modified": os.path.getmtime(file),
                    "content_preview": content[:200] + "..." if len(content) > 200 else content
                })
        except:
            pass
    
    return jsonify({
        "verification_files": files_info,
        "instructions": "Check the most recent file for your Gmail verification link"
    })

@app.route('/nutrition-summary')
def nutrition_summary():
    """Get nutrition summary from recent enhanced orders"""
    import glob
    from datetime import datetime, timedelta
    
    # Get enhanced order files from last 7 days
    recent_files = []
    cutoff_date = datetime.now() - timedelta(days=7)
    
    for file in glob.glob("enhanced_order_*.json"):
        try:
            # Extract timestamp from filename
            timestamp_str = file.replace("enhanced_order_", "").replace(".json", "")
            file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            
            if file_date >= cutoff_date:
                recent_files.append((file, file_date))
        except:
            continue
    
    if not recent_files:
        return jsonify({"message": "No recent enhanced orders found"})
    
    # Sort by date (most recent first)
    recent_files.sort(key=lambda x: x[1], reverse=True)
    
    total_nutrition = {
        'total_calories': 0,
        'total_protein': 0,
        'total_carbs': 0,
        'total_fat': 0,
        'total_sodium': 0,
        'total_cost': 0
    }
    
    orders = []
    
    for file_path, file_date in recent_files:
        try:
            with open(file_path, 'r') as f:
                order = json.load(f)
            
            meal_totals = order.get('meal_totals', {})
            
            # Add to running totals
            total_nutrition['total_calories'] += meal_totals.get('total_calories', 0)
            total_nutrition['total_protein'] += meal_totals.get('total_protein', 0)
            total_nutrition['total_carbs'] += meal_totals.get('total_carbs', 0)
            total_nutrition['total_fat'] += meal_totals.get('total_fat', 0)
            total_nutrition['total_sodium'] += meal_totals.get('total_sodium', 0)
            total_nutrition['total_cost'] += order.get('total', 0)
            
            # Count nutrition sources
            nutrition_sources = []
            for item in order.get('items', []):
                if item.get('nutrition') and item['nutrition'].get('source'):
                    nutrition_sources.append(item['nutrition']['source'])
            
            orders.append({
                'restaurant': order.get('restaurant'),
                'date': file_date.strftime('%Y-%m-%d %H:%M'),
                'total_cost': order.get('total'),
                'calories': meal_totals.get('total_calories', 0),
                'protein': meal_totals.get('total_protein', 0),
                'carbs': meal_totals.get('total_carbs', 0),
                'fat': meal_totals.get('total_fat', 0),
                'nutrition_sources': list(set(nutrition_sources))  # Unique sources
            })
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue
    
    # Calculate average daily nutrition (if multiple days)
    days_span = max(1, (recent_files[0][1] - recent_files[-1][1]).days + 1)
    
    return jsonify({
        "summary_period": f"Last {days_span} days",
        "total_orders": len(orders),
        "total_nutrition": total_nutrition,
        "daily_averages": {
            'avg_calories': round(total_nutrition['total_calories'] / days_span, 1),
            'avg_protein': round(total_nutrition['total_protein'] / days_span, 1),
            'avg_carbs': round(total_nutrition['total_carbs'] / days_span, 1),
            'avg_fat': round(total_nutrition['total_fat'] / days_span, 1),
            'avg_cost': round(total_nutrition['total_cost'] / days_span, 2)
        },
        "recent_orders": orders,
        "nutrition_source": "USDA FoodData Central API",
        "note": "All nutrition data sourced from USDA government database"
    })

@app.route('/cache-stats')
def cache_stats():
    """View nutrition cache statistics"""
    try:
        with open('nutrition_cache.json', 'r') as f:
            cache = json.load(f)
        
        # Analyze cache contents
        sources = {}
        total_items = len(cache)
        
        for key, data in cache.items():
            source = data.get('source', 'unknown')
            if source not in sources:
                sources[source] = 0
            sources[source] += 1
        
        return jsonify({
            "total_cached_items": total_items,
            "sources_breakdown": sources,
            "cache_file": "nutrition_cache.json",
            "note": "Cache helps avoid repeated USDA API calls for same food items"
        })
        
    except FileNotFoundError:
        return jsonify({
            "total_cached_items": 0,
            "message": "No cache file found yet - will be created after first nutrition lookup"
        })
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    print("🚀 Starting NutriSync with USDA API Integration...")
    print("📧 Ready for DoorDash order emails")
    print("🔐 Webhook signature verification enabled")
    print("🔗 Gmail verification link extraction enabled")
    print("🍎 USDA FoodData Central API nutrition tracking enabled")
    print("🔑 Using your USDA API key: YzTOpkjoupRbj0RJ7mzt5Jjp6igfFgg1uAz1u6rg")
    print("📄 Files saved:")
    print("   - gmail_verification_*.txt (Gmail setup)")
    print("   - order_*.json (original orders)")
    print("   - enhanced_order_*.json (with USDA nutrition)")
    print("   - nutrition_cache.json (API response cache)")
    print("🌐 Endpoints:")
    print("   - http://localhost:5000/ (home)")
    print("   - http://localhost:5000/test (test with paste.txt)")
    print("   - http://localhost:5000/nutrition-summary (recent nutrition)")
    print("   - http://localhost:5000/cache-stats (API cache stats)")
    app.run(debug=True, host='0.0.0.0', port=5000)