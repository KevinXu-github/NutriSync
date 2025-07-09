from flask import Flask, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def hello():
    return "🍔 NutriSync - DoorDash Order Parser"

@app.route('/webhook/email', methods=['POST'])
def handle_email():
    """Clean email webhook handler - essential output only"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n📧 EMAIL RECEIVED - {timestamp}")
    
    # Handle both JSON and form data
    email_data = {}
    
    if request.is_json:
        email_data = request.get_json()
    else:
        email_data = dict(request.form)
    
    # Get email data
    subject = email_data.get('subject', '')
    body = (email_data.get('stripped-html') or 
            email_data.get('body-html') or 
            email_data.get('stripped-text') or
            email_data.get('body-plain', ''))
    
    print(f"Subject: {subject}")
    
    # Quick DoorDash check
    if 'doordash' not in (subject + body).lower():
        print("⏭️  Not a DoorDash email, ignoring")
        return jsonify({"status": "ignored", "reason": "Not DoorDash"})
    
    # Parse the order
    try:
        from email_parser import parse_food_delivery_email
        
        result = parse_food_delivery_email(subject, body)
        
        if result:
            print(f"\n✅ ORDER PARSED SUCCESSFULLY!")
            print(f"🏪 Restaurant: {result['restaurant']}")
            print(f"💰 Total: ${result['total']}")
            print(f"🍔 Items ({len(result['items'])}):")
            
            for i, item in enumerate(result['items']):
                print(f"   {i+1}. {item['quantity']}x {item['name']} - ${item['price']}")
            
            # Save successful parse (keep this for your records)
            with open(f"order_{timestamp}.json", 'w') as f:
                json.dump(result, f, indent=2)
            
            # Try to log to MyFitnessPal (optional - will fail gracefully if not available)
            try:
                from myfitnesspal_logger import log_order_to_myfitnesspal
                print("\n🍽️ Logging to MyFitnessPal...")
                mfp_success = log_order_to_myfitnesspal(result)
                if mfp_success:
                    print("✅ MyFitnessPal logging successful")
                else:
                    print("⚠️ MyFitnessPal logging failed")
            except Exception as e:
                print(f"⚠️ MyFitnessPal not available: {e}")
            
            return jsonify({
                "status": "success",
                "restaurant": result['restaurant'],
                "total": result['total'],
                "items_count": len(result['items']),
                "timestamp": timestamp
            })
        else:
            print("❌ Could not parse DoorDash order")
            return jsonify({"status": "failed", "reason": "Parsing failed"})
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/test')
def test():
    """Test with your local file"""
    try:
        with open('paste.txt', 'r', encoding='utf-8') as f:
            body = f.read()
        
        subject = "Fwd: Order Confirmation for Kevin from McDonald's"
        
        from email_parser import parse_food_delivery_email
        result = parse_food_delivery_email(subject, body)
        
        if result:
            return jsonify({
                "status": "success",
                "message": "Local test successful",
                "restaurant": result['restaurant'],
                "total": result['total'],
                "items": result['items']
            })
        else:
            return jsonify({"status": "failed", "message": "Could not parse"})
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    print("🚀 Starting NutriSync DoorDash Parser...")
    print("📧 Ready to receive emails at your Mailgun address")
    app.run(debug=True, host='0.0.0.0', port=5000)