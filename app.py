from flask import Flask, render_template, request
import requests
import re
import time

app = Flask(__name__)

BASE_URL = "https://rvrjcce.ac.in/examcell/results/regnoresultsR1.php"

def search_results(prefixes, start, end, target_name, delay):
    results = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0"
    })

    for prefix in prefixes:
        for i in range(start, end + 1):
            reg_no = f"{prefix}{i:03d}"
            params = {"q": reg_no}

            try:
                response = session.get(BASE_URL, params=params, timeout=10)
                html = response.text

                match = re.search(r"Name\s*:\s*<b>(.*?)</b>", html)

                if match:
                    name = match.group(1).strip().upper()

                    if target_name.upper() in name:
                        results.append({
                            "reg_no": reg_no,
                            "name": name,
                            "status": "MATCH"
                        })
                    else:
                        results.append({
                            "reg_no": reg_no,
                            "name": name,
                            "status": "Checked"
                        })
                else:
                    results.append({
                        "reg_no": reg_no,
                        "name": "No Data",
                        "status": "No Data"
                    })

                time.sleep(delay)

            except Exception as e:
                results.append({
                    "reg_no": reg_no,
                    "name": "Error",
                    "status": str(e)
                })

    return results


@app.route("/", methods=["GET", "POST"])
def index():
    results = []

    if request.method == "POST":
        prefixes = request.form["prefixes"].split(",")
        start = int(request.form["start"])
        end = int(request.form["end"])
        target_name = request.form["target_name"]
        delay = float(request.form["delay"])

        results = search_results(prefixes, start, end, target_name, delay)

    return render_template("index.html", results=results)


if __name__ == "__main__":
    app.run(debug=True)