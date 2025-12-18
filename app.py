from flask import Flask, render_template, request, jsonify
from data import employees, parts
from datetime import datetime
import pandas as pd

wp_data = pd.read_csv("wp_data.csv")
header = wp_data.columns.tolist()

app = Flask(__name__)

attendance = {}  # key: "date_shift" value: {emp_id: bool}

@app.route("/")
def index():
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
        for emp_assign in assignment_employees[:]:  # copy to avoid modification during iteration
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

if __name__ == "__main__":
    app.run(debug=True)