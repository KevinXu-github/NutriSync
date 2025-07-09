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
    <h1>🍔 NutriSync - DoorDash Order Parser</h1>
    <h2>📧 Gmail Verification Helper</h2>
    <p>When you set up Gmail forwarding, check your console logs for the verification link!</p>
    <p>Recent verification links are also saved to <code>gmail_verification_*.txt</code> files.</p>
    """

@app.route('/webhook/email', methods=['POST'])
def handle_email():
    """Process incoming emails with enhanced Gmail verification handling"""
    
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
            
            # Save order
            order_file = f"order_{timestamp}.json"
            with open(order_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"📄 Order saved to: {order_file}")
            
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
                "timestamp": timestamp,
                "order_file": order_file
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

if __name__ == '__main__':
    print("🚀 Starting NutriSync...")
    print("📧 Ready for DoorDash order emails")
    print("🔐 Webhook signature verification enabled")
    print("🔗 Gmail verification link extraction enabled")
    print("📄 Verification links will be saved to gmail_verification_*.txt files")
    print("🌐 Visit http://localhost:5000/verification-files to see recent verification links")
    app.run(debug=True, host='0.0.0.0', port=5000)