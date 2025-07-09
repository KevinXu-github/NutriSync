from flask import Flask, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def hello():
    return "Food Tracker App - Email Webhook Ready"

@app.route('/webhook/email', methods=['POST'])
def handle_email():
    """Enhanced email webhook handler that logs everything Mailgun sends"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n=== EMAIL RECEIVED AT {timestamp} ===")
    
    # Log the content type
    print(f"Content-Type: {request.content_type}")
    
    # Log all headers
    print("\n--- HEADERS ---")
    for header, value in request.headers:
        print(f"{header}: {value}")
    
    # Handle both JSON and form data
    email_data = {}
    
    if request.is_json:
        print("\n--- JSON DATA ---")
        email_data = request.get_json()
        # Save raw JSON
        with open(f"mailgun_json_{timestamp}.json", 'w') as f:
            json.dump(email_data, f, indent=2)
        print(f"JSON data saved to mailgun_json_{timestamp}.json")
        
        # Log key fields
        for key, value in email_data.items():
            if key in ['body-html', 'body-plain', 'stripped-html', 'stripped-text']:
                print(f"{key}: {len(str(value))} characters")
                # Save full body content to file
                filename = f"mailgun_{key}_{timestamp}.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(str(value))
                print(f"  → Saved to {filename}")
            else:
                print(f"{key}: {value}")
    else:
        print("\n--- FORM DATA ---")
        for key, value in request.form.items():
            email_data[key] = value
            if key in ['body-html', 'body-plain', 'stripped-html', 'stripped-text']:
                print(f"{key}: {len(value)} characters")
                # Save full body content to file
                filename = f"mailgun_{key}_{timestamp}.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(value)
                print(f"  → Saved to {filename}")
            else:
                print(f"{key}: {value}")
    
    # Log raw data if any
    if request.data:
        print(f"\n--- RAW DATA ---")
        print(f"Raw data length: {len(request.data)}")
        with open(f"mailgun_raw_{timestamp}.txt", 'wb') as f:
            f.write(request.data)
    
    # Try to parse with our existing parser
    print("\n--- PARSING ATTEMPT ---")
    try:
        from email_parser import parse_food_delivery_email
        
        # Get email data from both JSON and form formats
        subject = email_data.get('subject', '')
        # Try stripped-html first, then body-html, then plain text
        body = (email_data.get('stripped-html') or 
                email_data.get('body-html') or 
                email_data.get('stripped-text') or
                email_data.get('body-plain', ''))
        
        print(f"Subject: {subject}")
        print(f"Body length: {len(body)}")
        print(f"Body preview: {body[:200]}...")
        
        # Try parsing
        result = parse_food_delivery_email(subject, body)
        
        if result:
            print("✓ Parsing SUCCESS!")
            print(f"Service: {result['service']}")
            print(f"Restaurant: {result['restaurant']}")
            print(f"Total: ${result['total']}")
            print(f"Items: {len(result['items'])}")
            
            # Save parsed result
            with open(f"parsed_result_{timestamp}.json", 'w') as f:
                json.dump(result, f, indent=2)
                
            return jsonify({
                "status": "success",
                "parsed": True,
                "restaurant": result['restaurant'],
                "total": result['total'],
                "items_count": len(result['items'])
            })
        else:
            print("✗ Parsing failed - not recognized as food delivery")
            return jsonify({
                "status": "ignored",
                "parsed": False,
                "reason": "Not a food delivery email"
            })
            
    except Exception as e:
        print(f"✗ Parsing error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/test')
def test():
    """Test endpoint to verify webhook is working"""
    return jsonify({
        "status": "webhook_ready",
        "message": "Send emails to test parsing",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("Starting Flask app for Mailgun testing...")
    print("Don't forget to:")
    print("1. Run 'ngrok http 5000' in another terminal")
    print("2. Configure Mailgun webhook with your ngrok URL")
    print("3. Forward a DoorDash email to your Mailgun address")
    app.run(debug=True, host='0.0.0.0', port=5000)