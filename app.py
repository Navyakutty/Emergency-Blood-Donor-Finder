from flask import Flask, render_template, request, jsonify
import datetime

app = Flask(__name__)

# Temporary Databases
donor_table = []
hospital_table = []
emergency_requests = []
hospital_data = {}

# --- HELPER FUNCTION: INVENTORY ---
def get_hosp_inventory(name):
    if name not in hospital_data:
        hospital_data[name] = {
            "A+": 5, "A-": 2, "B+": 8, "B-": 1, 
            "O+": 10, "O-": 2, "AB+": 4, "AB-": 0
        }
    return hospital_data[name]

# --- MAIN ROUTE ---
@app.route('/')
def home():
    return render_template('index.html')

# --- DONOR ROUTES ---
@app.route('/api/register-donor', methods=['POST'])
def register_donor():
    data = request.get_json()
    new_donor = {
        "id": len(donor_table) + 1,
        "name": data['name'],
        "blood_group": data['bloodGroup'],
        "phone": data['phone'],
        "profilePic": data.get('profilePic', ''),
        "badges": [],
        "history": []
    }
    donor_table.append(new_donor)
    return jsonify({"status": "success", "message": "Registered successfully!"})

@app.route('/api/login-donor', methods=['POST'])
def login_donor():
    phone = request.get_json().get('phone')
    donor = next((d for d in donor_table if d['phone'] == phone), None)
    if donor:
        return jsonify({"status": "success", "donor": donor})
    return jsonify({"status": "error", "message": "Donor not found. Please register!"})

@app.route('/api/donor-profile', methods=['POST'])
def donor_profile():
    phone = request.get_json().get('phone')
    donor = next((d for d in donor_table if d['phone'] == phone), None)
    return jsonify({"donor": donor})

# --- HOSPITAL ROUTES ---
@app.route('/api/login-hospital', methods=['POST'])
def login_hospital():
    name = request.get_json().get('hospitalName')
    return jsonify({"status": "success", "hospitalName": name, "inventory": get_hosp_inventory(name)})

# --- EMERGENCY & MATCHING ROUTES ---
@app.route('/api/emergency', methods=['POST'])
def trigger_emergency():
    data = request.get_json()
    new_request = {
        "id": len(emergency_requests) + 1, 
        "hospitalName": data['hospitalName'],
        "urgency": data['urgency'],
        "bloodGroup": data['bloodGroup'],
        "units": data['units'],
        "status": "pending",
        "last_cancel_reason": None
    }
    emergency_requests.append(new_request)
    return jsonify({"status": "success", "message": "Emergency broadcast sent!"})

@app.route('/api/get-emergencies', methods=['POST'])
def get_emergencies():
    donor_blood = request.get_json().get('bloodGroup')
    matched_reqs = [req for req in emergency_requests if req['status'] == 'pending' and req['bloodGroup'] == donor_blood]
    return jsonify({"emergencies": matched_reqs})

@app.route('/api/hospital-emergencies', methods=['POST'])
def hospital_emergencies():
    hosp_name = request.get_json().get('hospitalName')
    hosp_reqs = [req for req in emergency_requests if req['hospitalName'] == hosp_name]
    return jsonify({"emergencies": hosp_reqs[::-1]})

# --- MISSION ACTIONS (ACCEPT/CANCEL/COMPLETE) ---
@app.route('/api/accept-emergency', methods=['POST'])
def accept_emergency():
    data = request.get_json()
    req_id = data.get('id')
    donor_phone = data.get('donorPhone')
    
    donor = next((d for d in donor_table if d['phone'] == donor_phone), None)
    donor_name = donor['name'] if donor else "A Hero"
    donor_pic = donor['profilePic'] if donor else ""

    for req in emergency_requests:
        if req['id'] == req_id:
            req['status'] = 'accepted'
            req['acceptedBy'] = {"name": donor_name, "phone": donor_phone, "profilePic": donor_pic}
            req['last_cancel_reason'] = None
            break
    return jsonify({"status": "success"})

@app.route('/api/cancel-emergency', methods=['POST'])
def cancel_emergency():
    data = request.get_json()
    req_id = data.get('id')
    reason = data.get('reason')
    
    for req in emergency_requests:
        if req['id'] == req_id:
            req['status'] = 'pending'
            req.pop('acceptedBy', None)
            req['last_cancel_reason'] = reason
            break
    return jsonify({"status": "success", "message": "Hospital notified."})

@app.route('/api/hospital-cancel', methods=['POST'])
def hospital_cancel():
    req_id = request.get_json().get('id')
    global emergency_requests
    emergency_requests = [req for req in emergency_requests if req['id'] != req_id]
    return jsonify({"status": "success", "message": "Request closed."})

@app.route('/api/complete-donation', methods=['POST'])
def complete_donation():
    req_id = request.get_json().get('id')
    global emergency_requests
    
    req = next((r for r in emergency_requests if r['id'] == req_id), None)
    if req and 'acceptedBy' in req:
        donor_phone = req['acceptedBy']['phone']
        
        # Award Badge & Update History
        for donor in donor_table:
            if donor['phone'] == donor_phone:
                if "🏆 Verified Lifesaver" not in donor['badges']:
                    donor['badges'].append("🏆 Verified Lifesaver")
                
                date_str = datetime.datetime.now().strftime("%B %d, %Y")
                donor['history'].append({
                    "date": date_str,
                    "hospital": req['hospitalName'],
                    "bloodGroup": req['bloodGroup']
                })
                break
                
        # Auto-Increment Hospital Inventory
        inv = get_hosp_inventory(req['hospitalName'])
        inv[req['bloodGroup']] += 1
        
        # Remove request from active board
        emergency_requests = [r for r in emergency_requests if r['id'] != req_id]
        return jsonify({"status": "success", "inventory": inv})
        
    return jsonify({"status": "error"})

# --- INVENTORY MANAGEMENT (AUTO-ALERT LOGIC) ---
@app.route('/api/update-inventory', methods=['POST'])
def update_inventory():
    data = request.get_json()
    hosp_name = data.get('hospitalName')
    blood_type = data.get('bloodType')
    change = data.get('change') 
    
    inv = get_hosp_inventory(hosp_name)
    inv[blood_type] = max(0, inv[blood_type] + change)
    
    # Auto-publish emergency if stock falls below 2
    if inv[blood_type] < 2:
        exists = any(r for r in emergency_requests if r['hospitalName'] == hosp_name and r['bloodGroup'] == blood_type and r['status'] == 'pending')
        if not exists:
            new_request = {
                "id": len(emergency_requests)+1, "hospitalName": hosp_name, "urgency": "Critical (Auto-Alert)", 
                "bloodGroup": blood_type, "units": 2, "status": "pending"
            }
            emergency_requests.append(new_request)
            
    return jsonify({"status": "success", "inventory": inv})

if __name__ == '__main__':
    app.run(debug=True, port=5000)