import sys
import os
import json
import subprocess
from os import path
import re

current_dir = path.dirname(__file__)
parent_dir = path.dirname(current_dir)
sys.path.append(".")
sys.path.append(parent_dir)
from custom_components.vigieau.const import SENSOR_DEFINITIONS

file = os.path.join(parent_dir, "scripts/full_usage_list.json")
with open(file) as f:
    input = f.read()
data = json.loads(input)

new_matchers = { sensor.name: [] for sensor in SENSOR_DEFINITIONS }

for (i,restriction) in enumerate(data["restrictions"]):
    restriction["nom"] = restriction["usage"]
    matched = False
    for sensor in SENSOR_DEFINITIONS:
         if sensor.match(restriction):
             matched = True
             break
    if not matched:
        print(f"Restriction {restriction['usage']} not matched")
        print(restriction)
        # launch interactive fzf to select the sensor to add
        sensors = [sensor.name for sensor in SENSOR_DEFINITIONS]
        prompt = f"{i+1}/{len(data['restrictions'])}: {restriction['usage']} {restriction['thematique']}"
        selected_sensor = subprocess.run(["fzf", "--prompt", prompt], input="\n".join(sensors), capture_output=True, text=True)
        if selected_sensor.returncode != 0:
            print(f"No sensor selected")
            break
        name = selected_sensor.stdout.strip()
        if name in ["quit", "q", "exit", ""]:
            sys.exit(0)
        new_matchers[name].append(restriction)
        print(f"Added {restriction['usage']} to {name}")

def insert_new_matcher(sensor_name: str, matcher: str):
    file = os.path.join(parent_dir, "const.py")
    with open(file, "r") as f:
        content = f.read()
    content = content.split("\n")
    search_for_matchers = False
    insert_index = None
    for (i,line) in enumerate(content):
        if re.match(r'^\s*name="{}",\s*$'.format(sensor_name), line):
            search_for_matchers = True
        if search_for_matchers and re.match(r'^\s*matchers=\[\s*$', line):
            insert_index = i+1
            break
    
    content.insert(insert_index, f'"{matcher}",')
    with open(file, "w") as f:
        f.write("\n".join(content))

for sensor_name, usages in new_matchers.items():
    for usage in usages:
        r = usage["usage"].strip() + ".*" + usage['thematique'].strip()
        insert_new_matcher(sensor_name, r)
