from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def hello():
    return "Food Tracker App - Step 1"

@app.route('/webhook/email', methods=['POST'])
def handle_email():
    """Basic email webhook handler"""
    # For now, just print what we receive
    print("Received email webhook:")
    print("Form data:", request.form)
    print("JSON data:", request.get_json())
    
    return jsonify({"status": "received"})

if __name__ == '__main__':
    app.run(debug=True)