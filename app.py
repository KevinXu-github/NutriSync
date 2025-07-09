from flask import Flask, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def hello():
    return "🍔 NutriSync - DoorDash Order Parser"

@app.route('/webhook/email', methods=['POST'])
def handle_email():
    """Process incoming emails with enhanced filtering"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n📧 EMAIL RECEIVED - {timestamp}")
    
    # Get email data (handle both JSON and form data)
    email_data = request.get_json() if request.is_json else dict(request.form)
    
    subject = email_data.get('subject', '')
    sender = email_data.get('sender', '') or email_data.get('from', '')
    body = (email_data.get('stripped-html') or 
            email_data.get('body-html') or 
            email_data.get('stripped-text') or
            email_data.get('body-plain', ''))
    
    print(f"Subject: {subject}")
    
    try:
        from email_parser import should_process_email, parse_food_delivery_email
        
        # Filter email
        if not should_process_email(subject, body, sender):
            print("⏭️  Email filtered out")
            return jsonify({"status": "filtered", "reason": "Not a DoorDash order"})
        
        # Parse order
        result = parse_food_delivery_email(subject, body)
        
        if result:
            print(f"\n✅ ORDER PARSED!")
            print(f"🏪 Restaurant: {result['restaurant']}")
            print(f"💰 Total: ${result['total']}")
            print(f"🍔 Items ({len(result['items'])}):")
            
            for i, item in enumerate(result['items']):
                print(f"   {i+1}. {item['quantity']}x {item['name']} - ${item['price']}")
            
            # Save order
            with open(f"order_{timestamp}.json", 'w') as f:
                json.dump(result, f, indent=2)
            
            # Optional MyFitnessPal integration
            try:
                from myfitnesspal_logger import log_order_to_myfitnesspal
                print("\n🍽️ Logging to MyFitnessPal...")
                if log_order_to_myfitnesspal(result):
                    print("✅ MyFitnessPal success")
                else:
                    print("⚠️ MyFitnessPal failed")
            except ImportError:
                print("⚠️ MyFitnessPal not available")
            
            return jsonify({
                "status": "success",
                "restaurant": result['restaurant'],
                "total": result['total'],
                "items_count": len(result['items']),
                "timestamp": timestamp
            })
        else:
            print("❌ Parsing failed")
            return jsonify({"status": "failed", "reason": "Parsing failed"})
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/test')
def test():
    """Test with local file"""
    try:
        with open('paste.txt', 'r', encoding='utf-8') as f:
            body = f.read()
        
        subject = "Fwd: Order Confirmation for Kevin from Jack in the Box"
        sender = "xuk654@gmail.com"
        
        from email_parser import should_process_email, parse_food_delivery_email
        
        print(f"\n🧪 LOCAL TEST - {subject}")
        
        if should_process_email(subject, body, sender):
            result = parse_food_delivery_email(subject, body)
            if result:
                return jsonify({
                    "status": "success",
                    "restaurant": result['restaurant'],
                    "total": result['total'],
                    "items": result['items']
                })
            else:
                return jsonify({"status": "failed", "message": "Parsing failed"})
        else:
            return jsonify({"status": "filtered", "message": "Email filtered out"})
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    print("🚀 Starting NutriSync...")
    print("📧 Ready for DoorDash order emails")
    app.run(debug=True, host='0.0.0.0', port=5000)