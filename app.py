import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from flask import jsonify
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')
app.config['SESSION_TYPE'] = 'filesystem'

# File paths
DATA_FILE = 'substation_data.db'
AUDIT_LOG = 'audit_log.db'
USER_FILE = 'users.db'

# Initialize data files
def initialize_files():
    """Create data files with default structure if they don't exist"""
    # Main data file
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({"substations": []}, f, indent=4)
    
    # Audit log
    if not os.path.exists(AUDIT_LOG):
        with open(AUDIT_LOG, 'w') as f:
            json.dump({"logs": []}, f, indent=4)
    
    # User credentials (demo users)
    if not os.path.exists(USER_FILE):
        with open(USER_FILE, 'w') as f:
            users = {
                "admin": {"password": "admin123", "role": "admin"},
                "operator": {"password": "operator123", "role": "operator"}
            }
            json.dump(users, f, indent=4)

# User authentication and authorization
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash('Admin privileges required for this action', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def log_audit(action, details):
    """Log user actions for auditing"""
    try:
        if not os.path.exists(AUDIT_LOG):
            initialize_files()
            
        with open(AUDIT_LOG, 'r') as f:
            data = json.load(f)
            
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user": session.get('username', 'unknown'),
            "action": action,
            "details": details
        }
        
        data["logs"].append(log_entry)
        
        with open(AUDIT_LOG, 'w') as f:
            json.dump(data, f, indent=4)
            
    except Exception as e:
        print(f"Audit log error: {str(e)}")

# Data handling functions (load_data, save_data, get_stats, get_detailed_stats remain mostly the same)
def initialize_data_file():
    """Create data file with default structure if it doesn't exist"""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({"substations": []}, f, indent=4)

def load_data():
    """Load data from JSON file with error handling"""
    try:
        if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        else:
            initialize_data_file()
            return {"substations": []}
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading data: {e}")
        return {"substations": []}

def save_data(data):
    """Save data to JSON file"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        print(f"Error saving data: {e}")

def get_stats():
    data = load_data()
    stats = {
        "substation_count": 0,
        "bay_count": 0,
        "switchyard_equipment_count": 0,
        "switchyard_failed": 0,
        "control_room_equipment_count": 0,
        "control_room_failed": 0,
        "healthy_count": 0,
        "critical_count": 0
    }
    
    for substation in data.get("substations", []):
        stats["substation_count"] += 1
        for bay in substation.get("bays", []):
            stats["bay_count"] += 1
            for equipment in bay.get("switchyard_equipment", []):
                stats["switchyard_equipment_count"] += 1
                if equipment.get("status") == "Failed":
                    stats["switchyard_failed"] += 1
            for device in bay.get("control_room_devices", []):
                stats["control_room_equipment_count"] += 1
                if device.get("status") == "Failed":
                    stats["control_room_failed"] += 1
                    
    stats["healthy_count"] = stats["substation_count"] * 2
    stats["critical_count"] = stats["switchyard_failed"] + stats["control_room_failed"]
    
    return stats

def get_detailed_stats():
    data = load_data()
    stats = get_stats()
    
    # Calculate system health
    total_equipment = stats["switchyard_equipment_count"] + stats["control_room_equipment_count"]
    failed_equipment = stats["switchyard_failed"] + stats["control_room_failed"]
    system_health = 100 - (failed_equipment / total_equipment * 100) if total_equipment > 0 else 100
    
    # Prepare substation health data
    substations_health = []
    for substation in data.get("substations", []):
        failed_count = 0
        total_equipment = 0
        for bay in substation.get("bays", []):
            total_equipment += len(bay.get("switchyard_equipment", [])) + len(bay.get("control_room_devices", []))
            for equipment in bay.get("switchyard_equipment", []):
                if equipment.get("status") == "Failed":
                    failed_count += 1
            for device in bay.get("control_room_devices", []):
                if device.get("status") == "Failed":
                    failed_count += 1
        
        health_score = max(0, 100 - (failed_count / total_equipment * 100)) if total_equipment > 0 else 100
        substations_health.append({
            "name": substation["name"],
            "location": substation["location"],
            "health_score": round(health_score, 1),
            "failed_count": failed_count,
            "total_equipment": total_equipment,
            "operational_count": total_equipment - failed_count
        })
    
    # Prepare failed devices data
    failed_devices = []
    for substation in data.get("substations", []):
        for bay in substation.get("bays", []):
            for equipment in bay.get("switchyard_equipment", []):
                if equipment.get("status") == "Failed":
                    failed_devices.append({
                        "substation": substation["name"],
                        "bay": bay["name"],
                        "equipment": equipment["name"],
                        "type": equipment["type"],
                        "substation_id": substation["id"],
                        "bay_id": bay["id"],
                        "status": "Failed"
                    })
            for device in bay.get("control_room_devices", []):
                if device.get("status") == "Failed":
                    failed_devices.append({
                        "substation": substation["name"],
                        "bay": bay["name"],
                        "equipment": device["name"],
                        "type": device["type"],
                        "substation_id": substation["id"],
                        "bay_id": bay["id"],
                        "status": "Failed"
                    })
    
    # Group same device failures
    device_failures = {}
    for device in failed_devices:
        key = device["type"]
        if key not in device_failures:
            device_failures[key] = []
        device_failures[key].append(device)
    
    # Prepare all devices data
    all_devices = []
    for substation in data.get("substations", []):
        for bay in substation.get("bays", []):
            for equipment in bay.get("switchyard_equipment", []):
                all_devices.append({
                    "substation": substation["name"],
                    "bay": bay["name"],
                    "equipment": equipment["name"],
                    "type": equipment["type"],
                    "status": equipment.get("status", "OK")
                })
            for device in bay.get("control_room_devices", []):
                all_devices.append({
                    "substation": substation["name"],
                    "bay": bay["name"],
                    "equipment": device["name"],
                    "type": device["type"],
                    "status": device.get("status", "OK")
                })
    
    # Prepare failures by location
    location_failures = {"substation": {}, "bay": {}}
    for device in failed_devices:
        # Group by substation
        substation_key = device["substation"]
        if substation_key not in location_failures["substation"]:
            location_failures["substation"][substation_key] = 0
        location_failures["substation"][substation_key] += 1
        
        # Group by bay
        bay_key = f"{device['substation']} | {device['bay']}"
        if bay_key not in location_failures["bay"]:
            location_failures["bay"][bay_key] = 0
        location_failures["bay"][bay_key] += 1
    
    # Prepare device ratings (using status as a placeholder)
    device_ratings = {}
    for device in all_devices:
        key = device["type"]
        if key not in device_ratings:
            device_ratings[key] = {"count": 0, "failed": 0}
        device_ratings[key]["count"] += 1
        if device["status"] == "Failed":
            device_ratings[key]["failed"] += 1
    
    return {
        "system_health": round(system_health, 1),
        "operational_devices": stats["switchyard_equipment_count"] + stats["control_room_equipment_count"] - failed_equipment,
        "failed_devices_count": failed_equipment,
        "substation_count": stats["substation_count"],
        "substations_health": substations_health,
        "failed_devices": failed_devices,
        "device_failures": device_failures,
        "all_devices": all_devices,
        "location_failures": location_failures,
        "device_ratings": device_ratings
    }
initialize_files()
initialize_data_file()

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            with open(USER_FILE, 'r') as f:
                users = json.load(f)
                
            if username in users and users[username]['password'] == password:
                session['username'] = username
                session['role'] = users[username]['role']
                flash('Login successful!', 'success')
                log_audit("login", f"User {username} logged in")
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'danger')
                
        except Exception as e:
            flash(f'Error accessing user database: {str(e)}', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', 'unknown')
    session.clear()
    log_audit("logout", f"User {username} logged out")
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/')
#@login_required
def dashboard():
    view = request.args.get('view', 'new')  # Default to new view
    detailed_stats = get_detailed_stats()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #detailed_stats['current_user'] = {
    #    'username': session['username'],
     #   'role': session['role']
    #}
    return render_template('dashboard_new.html', current_time=current_time, stats=detailed_stats)


@app.route('/substations')
@login_required
def substations():
    data = load_data()
    for substation in data["substations"]:
        total_failed = 0
        total_equipment = 0
        for bay in substation["bays"]:
            total_equipment += len(bay["switchyard_equipment"]) + len(bay["control_room_devices"])
            for equipment in bay["switchyard_equipment"]:
                if equipment["status"] == "Failed":
                    total_failed += 1
            for device in bay["control_room_devices"]:
                if device["status"] == "Failed":
                    total_failed += 1
        health_score = max(0, 100 - (total_failed / total_equipment * 100)) if total_equipment > 0 else 100
        substation["health_score"] = round(health_score, 1)
    
    return render_template('substations.html', substations=data["substations"], is_admin=(session['role'] == 'admin'))

@app.route('/substation/<int:substation_id>')
@login_required
def substation_detail(substation_id):
    data = load_data()
    substation = next((s for s in data["substations"] if s["id"] == substation_id), None)
    if not substation:
        flash("Substation not found", "danger")
        return redirect(url_for('substations'))
    
    for bay in substation.get("bays", []):
        bay_failed = 0
        bay_total = len(bay.get("switchyard_equipment", [])) + len(bay.get("control_room_devices", []))
        
        for equipment in bay.get("switchyard_equipment", []):
            if equipment.get("status") == "Failed":
                bay_failed += 1
        for device in bay.get("control_room_devices", []):
            if device.get("status") == "Failed":
                bay_failed += 1
        
        bay["health_score"] = max(0, 100 - (bay_failed / bay_total * 100)) if bay_total > 0 else 100
        bay["failed_count"] = bay_failed
        bay["total_equipment"] = bay_total
    
    total_failed = sum(bay.get("failed_count", 0) for bay in substation.get("bays", []))
    total_equipment = sum(bay.get("total_equipment", 0) for bay in substation.get("bays", []))
    health_score = max(0, 100 - (total_failed / total_equipment * 100)) if total_equipment > 0 else 100
    
    return render_template('substation_detail.html', 
                           substation=substation,
                           health_score=round(health_score, 1),
                           failed_count=total_failed,
                           total_equipment=total_equipment)

@app.route('/add_substation', methods=['GET', 'POST'])
@login_required
@admin_required
def add_substation():
    if request.method == 'POST':
        data = load_data()
        new_id = max([s["id"] for s in data["substations"]], default=0) + 1
        
        substation = {
            "id": new_id,
            "name": request.form["name"],
            "location": request.form["location"],
            "voltage_level": request.form["voltage_level"],
            "bays": []
        }
        
        data["substations"].append(substation)
        save_data(data)
        flash("Substation added successfully!", "success")
        return redirect(url_for('substations'))
    
    return render_template('add_substation.html')

@app.route('/substation/<int:substation_id>/add_bay', methods=['GET', 'POST'])
@login_required
@admin_required
def add_bay(substation_id):
    if request.method == 'POST':
        data = load_data()
        substation = next((s for s in data["substations"] if s["id"] == substation_id), None)
        if not substation:
            flash("Substation not found", "danger")
            return redirect(url_for('substations'))
            
        new_bay_id = max([b["id"] for b in substation["bays"]], default=0) + 1
        
        bay = {
            "id": new_bay_id,
            "name": request.form["name"],
            "type": request.form["type"],
            "switchyard_equipment": [],
            "control_room_devices": []
        }
        
        substation["bays"].append(bay)
        save_data(data)
        flash("Bay added successfully!", "success")
        return redirect(url_for('substation_detail', substation_id=substation_id))
    
    return render_template('add_bay.html', substation_id=substation_id)

@app.route('/substation/<int:substation_id>/bay/<int:bay_id>/add_equipment', methods=['GET', 'POST'])
@login_required
@admin_required
def add_equipment(substation_id, bay_id):
    valid_equipment_types = ['switchyard_equipment', 'control_room_devices']
    
    if request.method == 'POST':
        data = load_data()
        substation = next((s for s in data["substations"] if s["id"] == substation_id), None)
        if not substation:
            flash("Substation not found", "danger")
            return redirect(url_for('substations'))
            
        bay = next((b for b in substation["bays"] if b["id"] == bay_id), None)
        if not bay:
            flash("Bay not found", "danger")
            return redirect(url_for('substation_detail', substation_id=substation_id))
        
        equipment_type = request.form["equipment_type"]
        if equipment_type not in valid_equipment_types:
            flash("Invalid equipment type", "danger")
            return redirect(url_for('substation_detail', substation_id=substation_id))
        
        new_item = {
            "id": max([e["id"] for e in bay[equipment_type]], default=0) + 1,
            "name": request.form["name"],
            "type": request.form["type"],
            "specifications": request.form["specifications"],
            "status": "OK"
        }
        
        bay[equipment_type].append(new_item)
        save_data(data)
        flash(f"{equipment_type.replace('_', ' ').title()} added successfully!", "success")
        return redirect(url_for('substation_detail', substation_id=substation_id))
    
    else:
        equipment_type = request.args.get('equipment_type')
        if equipment_type not in valid_equipment_types:
            flash("Invalid equipment type", "danger")
            return redirect(url_for('substation_detail', substation_id=substation_id))
        
        return render_template('add_equipment.html', 
                              substation_id=substation_id, 
                              bay_id=bay_id,
                              equipment_type=equipment_type)

@app.route('/update_status', methods=['POST'])
@login_required
@admin_required
def update_status():
    valid_equipment_types = ['switchyard_equipment', 'control_room_devices']
    
    data = load_data()
    substation_id = int(request.form["substation_id"])
    bay_id = int(request.form["bay_id"])
    equipment_type = request.form["equipment_type"]
    equipment_id = int(request.form["equipment_id"])
    new_status = request.form["new_status"]
    
    if equipment_type not in valid_equipment_types:
        flash("Invalid equipment type", "danger")
        return redirect(url_for('substations'))
    
    substation = next((s for s in data["substations"] if s["id"] == substation_id), None)
    if not substation:
        flash("Substation not found", "danger")
        return redirect(url_for('substations'))
        
    bay = next((b for b in substation["bays"] if b["id"] == bay_id), None)
    if not bay:
        flash("Bay not found", "danger")
        return redirect(url_for('substation_detail', substation_id=substation_id))
    
    equipment = next((e for e in bay[equipment_type] if e["id"] == equipment_id), None)
    if equipment:
        equipment["status"] = new_status
        save_data(data)
        flash("Status updated successfully!", "success")
    else:
        flash("Equipment not found", "danger")
    
    return redirect(url_for('substation_detail', substation_id=substation_id))

@app.route('/api/failed_devices')
@login_required
def get_failed_devices():
    data = load_data()
    failed_devices = []
    
    for substation in data["substations"]:
        for bay in substation["bays"]:
            for equipment in bay["switchyard_equipment"]:
                if equipment["status"] == "Failed":
                    failed_devices.append({
                        "substation": substation["name"],
                        "bay": bay["name"],
                        "equipment": equipment["name"],
                        "type": equipment["type"],
                        "substation_id": substation["id"],
                        "bay_id": bay["id"],
                        "equipment_id": equipment["id"]
                    })
            for device in bay["control_room_devices"]:
                if device["status"] == "Failed":
                    failed_devices.append({
                        "substation": substation["name"],
                        "bay": bay["name"],
                        "equipment": device["name"],
                        "type": device["type"],
                        "substation_id": substation["id"],
                        "bay_id": bay["id"],
                        "equipment_id": device["id"]
                    })
    
    return jsonify(failed_devices)

@app.route('/api/substation_health')
@login_required
def get_substation_health():
    data = load_data()
    health_data = []
    
    for substation in data["substations"]:
        failed_count = 0
        total_equipment = 0
        
        for bay in substation["bays"]:
            total_equipment += len(bay["switchyard_equipment"]) + len(bay["control_room_devices"])
            for equipment in bay["switchyard_equipment"]:
                if equipment["status"] == "Failed":
                    failed_count += 1
            for device in bay["control_room_devices"]:
                if device["status"] == "Failed":
                    failed_count += 1
        
        health_score = max(0, 100 - (failed_count / total_equipment * 100)) if total_equipment > 0 else 100
        health_data.append({
            "id": substation["id"],
            "name": substation["name"],
            "location": substation["location"],
            "health_score": round(health_score, 1),
            "failed_count": failed_count,
            "total_equipment": total_equipment
        })
    
    return jsonify(health_data)

@app.route('/delete_substation/<int:substation_id>', methods=['POST'])
@login_required
@admin_required
def delete_substation(substation_id):
    try:
        data = load_data()
        substation = next((s for s in data["substations"] if s["id"] == substation_id), None)
        
        if substation:
            data["substations"] = [s for s in data["substations"] if s["id"] != substation_id]
            save_data(data)
            log_audit("delete_substation", f"Deleted substation {substation['name']} (ID: {substation_id})")
            flash("Substation deleted successfully!", "success")
        else:
            flash("Substation not found", "danger")
            
    except Exception as e:
        flash(f"Error deleting substation: {str(e)}", "danger")
    
    return redirect(url_for('substations'))

@app.route('/delete_bay/<int:substation_id>/<int:bay_id>', methods=['POST'])
@login_required
@admin_required
def delete_bay(substation_id, bay_id):
    data = load_data()
    substation = next((s for s in data["substations"] if s["id"] == substation_id), None)
    if substation:
        substation["bays"] = [b for b in substation["bays"] if b["id"] != bay_id]
        save_data(data)
        flash("Bay deleted successfully!", "success")
    return redirect(url_for('substation_detail', substation_id=substation_id))

@app.route('/delete_equipment/<int:substation_id>/<int:bay_id>/<equipment_type>/<int:equipment_id>', methods=['POST'])
@login_required
@admin_required
def delete_equipment(substation_id, bay_id, equipment_type, equipment_id):
    data = load_data()
    substation = next((s for s in data["substations"] if s["id"] == substation_id), None)
    if substation:
        bay = next((b for b in substation["bays"] if b["id"] == bay_id), None)
        if bay:
            bay[equipment_type] = [e for e in bay[equipment_type] if e["id"] != equipment_id]
            save_data(data)
            flash("Equipment deleted successfully!", "success")
    return redirect(url_for('substation_detail', substation_id=substation_id))

@app.route('/edit_substation/<int:substation_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_substation(substation_id):
    data = load_data()
    substation = next((s for s in data["substations"] if s["id"] == substation_id), None)
    
    if not substation:
        flash("Substation not found", "danger")
        return redirect(url_for('substations'))
    
    if request.method == 'POST':
        substation["name"] = request.form["name"]
        substation["location"] = request.form["location"]
        substation["voltage_level"] = request.form["voltage_level"]
        save_data(data)
        flash("Substation updated successfully!", "success")
        return redirect(url_for('substation_detail', substation_id=substation_id))
    
    return render_template('edit_substation.html', substation=substation)

@app.route('/edit_bay/<int:substation_id>/<int:bay_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_bay(substation_id, bay_id):
    data = load_data()
    substation = next((s for s in data["substations"] if s["id"] == substation_id), None)
    if not substation:
        flash("Substation not found", "danger")
        return redirect(url_for('substations'))
    
    bay = next((b for b in substation["bays"] if b["id"] == bay_id), None)
    if not bay:
        flash("Bay not found", "danger")
        return redirect(url_for('substation_detail', substation_id=substation_id))
    
    if request.method == 'POST':
        bay["name"] = request.form["name"]
        bay["type"] = request.form["type"]
        save_data(data)
        flash("Bay updated successfully!", "success")
        return redirect(url_for('substation_detail', substation_id=substation_id))
    
    return render_template('edit_bay.html', substation_id=substation_id, bay=bay)

@app.route('/edit_equipment/<int:substation_id>/<int:bay_id>/<equipment_type>/<int:equipment_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_equipment(substation_id, bay_id, equipment_type, equipment_id):
    data = load_data()
    substation = next((s for s in data["substations"] if s["id"] == substation_id), None)
    if not substation:
        flash("Substation not found", "danger")
        return redirect(url_for('substations'))
    
    bay = next((b for b in substation["bays"] if b["id"] == bay_id), None)
    if not bay:
        flash("Bay not found", "danger")
        return redirect(url_for('substation_detail', substation_id=substation_id))
    
    equipment = next((e for e in bay[equipment_type] if e["id"] == equipment_id), None)
    if not equipment:
        flash("Equipment not found", "danger")
        return redirect(url_for('substation_detail', substation_id=substation_id))
    
    if request.method == 'POST':
        equipment["name"] = request.form["name"]
        equipment["type"] = request.form["type"]
        equipment["specifications"] = request.form["specifications"]
        save_data(data)
        flash("Equipment updated successfully!", "success")
        return redirect(url_for('substation_detail', substation_id=substation_id))
    
    return render_template('edit_equipment.html', 
                          substation_id=substation_id,
                          bay_id=bay_id,
                          equipment_type=equipment_type,
                          equipment=equipment)

@app.route('/api/equipment_health_stats')
@login_required
def get_equipment_health_stats():
    data = load_data()
    stats = {
        "switchyard": {"ok": 0, "failed": 0},
        "control_room": {"ok": 0, "failed": 0}
    }
    
    for substation in data["substations"]:
        for bay in substation["bays"]:
            for equipment in bay["switchyard_equipment"]:
                if equipment["status"] == "OK":
                    stats["switchyard"]["ok"] += 1
                else:
                    stats["switchyard"]["failed"] += 1
            for device in bay["control_room_devices"]:
                if device["status"] == "OK":
                    stats["control_room"]["ok"] += 1
                else:
                    stats["control_room"]["failed"] += 1
    
    return jsonify(stats)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)