from flask import Flask, render_template, request, jsonify
import pandas as pd
import requests
from io import StringIO
import os

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Employee data
employees = {
    "E001": {"name": "E Vikram Kumar", "efficiency": 0.95, "trained_skills": "PAA,Paint_Booth"},
    "E002": {"name": "Yallaling", "efficiency": 0.9, "trained_skills": "Prefit,CCA"},
    "E003": {"name": "Chinni", "efficiency": 0.5, "trained_skills": "Autoclave,Debagging"},
    "E004": {"name": "M Imran", "efficiency": 0.8, "trained_skills": "PAA,Paint_Booth"},
    "E005": {"name": "Daharmendar", "efficiency": 0.75, "trained_skills": "Paint_Booth,"},
    "E006": {"name": "Satishkumar", "efficiency": 0.6, "trained_skills": "Autoclave,Debbaging"},
    "E007": {"name": "Kishor", "efficiency": 0.85, "trained_skills": "Prefit,CCA"},
    "E008": {"name": "Shiva Karan", "efficiency": 0.7, "trained_skills": "Paint_Booth,"},
    "E009": {"name": "Ganesh Patil", "efficiency": 0.65, "trained_skills": "PAA,Paint Booth"},
    "E010": {"name": "Malleshi", "efficiency": 0.9, "trained_skills": "Debbaging"},
    "E011": {"name": "Kanhu", "efficiency": 0.9, "trained_skills": "Prefit,CCA"},
    "E012": {"name": "Ajith Kumar", "efficiency": 0.7, "trained_skills": "Prefit,CCA"},
    "E013": {"name": "Manoj Kumar", "efficiency": 0.8, "trained_skills": "Paint Booth"},
    "E014": {"name": "R Raju", "efficiency": 0.8, "trained_skills": "Paint Booth"},
    "E015": {"name": "Arun Kumar", "efficiency": 0.4, "trained_skills": "Prefit,CCA"},
    "E016": {"name": "Harish", "efficiency": 0.8, "trained_skills": "Prefit,CCA"},
    "E017": {"name": "Adithya", "efficiency": 0.5, "trained_skills": "Debbaging"},
    "E018": {"name": "Jaswa", "efficiency": 0.7, "trained_skills": "Paint_Booth"},
    "E019": {"name": "Mende", "efficiency": 0.6, "trained_skills": "Paint_Booth"},
    "E020": {"name": "Jhanak", "efficiency": 0.9, "trained_skills": "Prefit,CCA"},
    "E021": {"name": "Prameela", "efficiency": 0.7, "trained_skills": "Prefit,CCA"},
    "E022": {"name": "Laxmii", "efficiency": 0.6, "trained_skills": "Prefit,CCA"},
    "E023": {"name": "Sumitra", "efficiency": 0.6, "trained_skills": "Prefit,CCA"},
}

parts = {
    "Piston-101": {"name": "352676A3R"},
    "Gear-205": {"name": "352676A3L"},
    "Shaft-301": {"name": "370057-1P"},
    "Bracket-X": {"name": "370047A500"},
}

# GitHub raw URL for CSV data - UPDATE THIS WITH YOUR ACTUAL GITHUB RAW URL
GITHUB_CSV_URL = "https://raw.githubusercontent.com/Vinishkrishna/management/main/wp_data.csv"

def fetch_wp_data():
    """Fetch CSV data from GitHub"""
    try:
        response = requests.get(GITHUB_CSV_URL)
        response.raise_for_status()
        csv_data = StringIO(response.text)
        return pd.read_csv(csv_data)
    except Exception as e:
        print(f"Error fetching CSV from GitHub: {e}")
        # Fallback data
        fallback_data = """parts,prefit,CCA,PAA,Paint_Booth,Autoclave
Piston-101,480,420,410,400,360
Gear-205,520,610,465,412,670
Shaft-301,475,420,370,400,513
Bracket-X,560,515,464,700,438"""
        return pd.read_csv(StringIO(fallback_data))

# Global cache for wp_data
_wp_data_cache = None

def get_wp_data():
    global _wp_data_cache
    if _wp_data_cache is None:
        _wp_data_cache = fetch_wp_data()
    return _wp_data_cache

attendance = {}  # key: "date_shift" value: {emp_id: bool}

@app.route("/")
def index():
    wp_data = get_wp_data()
    header = wp_data.columns.tolist()
    return render_template("index.html", employees=employees, parts=parts, header=header[1:])

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    data = request.get_json()
    date = data.pop('date')
    shift = data.pop('shift')
    key = f"{date}_{shift}"
    attendance[key] = {}
    for emp_id, present in data.items():
        attendance[key][emp_id] = present
    return jsonify({"status": "success", "attendance": attendance[key]})

@app.route("/plan_production", methods=["POST"])
def plan_production():
    wp_data = get_wp_data()
    header = wp_data.columns.tolist()
    
    data = request.get_json()
    selected_parts = data["parts"]
    date = data['date']
    shift = data['shift']
    key = f"{date}_{shift}"
    present_dict = attendance.get(key, {})
    present_employees = [
        {"id": eid, "name": emp["name"], "efficiency": emp["efficiency"], "trained_skills": emp["trained_skills"]}
        for eid, emp in employees.items() if present_dict.get(eid, False)
    ]
    present_employees.sort(key=lambda x: x["efficiency"], reverse=True)

    total_tasks = []
    for item in selected_parts:
        part_id = item["part_id"]
        qty = int(item["quantity"])
        area = item["work_area"]
        time_per_unit_min = wp_data.loc[wp_data[header[0]] == part_id, area].values
        part = parts[part_id]
        total_minutes = time_per_unit_min[0] * qty if len(time_per_unit_min) > 0 else 0
        total_tasks.append({
            "part_name": part["name"],
            "part_id": part_id,
            "quantity": qty,
            "work_area": area,
            "total_minutes": total_minutes,
            "time_per_unit": time_per_unit_min[0] if len(time_per_unit_min) > 0 else 0
        })

    assignments = []
    total_tasks.sort(key=lambda x: x["total_minutes"], reverse=True)
    assignment_employees = present_employees.copy()

    for task in total_tasks:
        task_assignments = []
        best_operator = None
        support_operator = None
        last_best_efficiency = -float('inf')
        last_support_efficiency = float('inf')
        for emp_assign in assignment_employees[:]:
            skills = [s.strip() for s in emp_assign["trained_skills"].split(",")]
            if task['work_area'] in skills and emp_assign["efficiency"] > last_best_efficiency:
                best_operator = emp_assign
                last_best_efficiency = emp_assign["efficiency"]

        if best_operator:
            assignment_employees.remove(best_operator)

        for emp_assign in assignment_employees[:]:
            skills = [s.strip() for s in emp_assign["trained_skills"].split(",")]
            if task['work_area'] in skills and emp_assign["efficiency"] < last_support_efficiency:
                support_operator = emp_assign
                last_support_efficiency = emp_assign["efficiency"]

        if support_operator:
            assignment_employees.remove(support_operator)

        if best_operator:
            task_assignments.append({
                "best_operator": best_operator["name"],
                "support_operator": support_operator["name"] if support_operator else "None"
            })

        assignments.append({
            "part": task["part_name"],
            "quantity": task["quantity"],
            "work_area": task["work_area"],
            "operators": task_assignments
        })

    return jsonify({"assignments": assignments, "present_count": len(present_employees)})

# Vercel serverless handler
if __name__ == "__main__":
    app.run(debug=True)
