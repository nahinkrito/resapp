from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import asyncio
import httpx
import re
import os
import json

app = FastAPI()
templates = Jinja2Templates(directory="templates")

BASE_URL = "https://rvrjcce.ac.in/examcell/results/regnoresultsR1.php"

DATA_FOLDER = "data"
os.makedirs(DATA_FOLDER, exist_ok=True)

# ===== GLOBAL STATE =====
state = {
    "running": False,
    "paused": False,
    "stop": False,
    "current": "",
    "checked": 0,
    "total": 0,
    "matches": [],
    "mode": "live"  # live or local
}


# ================= HOME =================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ================= START LIVE SCAN =================
@app.post("/start")
async def start_scan(data: dict):
    if state["running"]:
        return {"error": "Already running"}

    prefixes = data["prefixes"]
    start = int(data["start"])
    end = int(data["end"])
    delay = float(data["delay"])
    target_name = data["target_name"].upper()
    concurrency = int(data.get("concurrency", 5))

    state.update({
        "running": True,
        "paused": False,
        "stop": False,
        "checked": 0,
        "matches": [],
        "mode": "live"
    })

    state["total"] = len(prefixes) * (end - start + 1)

    asyncio.create_task(
        scan(prefixes, start, end, delay, target_name, concurrency)
    )

    return {"status": "started"}


# ================= LIVE SCAN =================
async def scan(prefixes, start, end, delay, target_name, concurrency):

    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=15) as client:

        async def fetch(prefix, i):
            async with semaphore:

                if state["stop"]:
                    return

                while state["paused"]:
                    await asyncio.sleep(0.5)

                file_path = f"{DATA_FOLDER}/{prefix}.json"

                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        data = json.load(f)
                else:
                    data = {"last_checked": start - 1, "records": {}}

                if i <= data["last_checked"]:
                    return

                reg_no = f"{prefix}{i:03d}"
                state["current"] = reg_no

                try:
                    r = await client.get(BASE_URL, params={"q": reg_no})
                    html = r.text

                    match = re.search(r"Name\s*:\s*<b>(.*?)</b>", html)

                    if match:
                        name = match.group(1).strip().upper()
                        data["records"][reg_no] = name

                        if target_name in name:
                            state["matches"].append({
                                "reg_no": reg_no,
                                "name": name
                            })
                    else:
                        data["records"][reg_no] = "NO DATA"

                except:
                    data["records"][reg_no] = "ERROR"

                data["last_checked"] = i

                with open(file_path, "w") as f:
                    json.dump(data, f)

                state["checked"] += 1
                await asyncio.sleep(delay)

        tasks = []

        for prefix in prefixes:
            for i in range(start, end + 1):
                if state["stop"]:
                    break
                tasks.append(fetch(prefix, i))

        await asyncio.gather(*tasks)

    state["running"] = False


# ================= LOCAL SEARCH =================
@app.post("/search_local")
async def search_local(data: dict):
    prefix = data["prefix"]
    name_query = data["name"].upper()

    file_path = f"{DATA_FOLDER}/{prefix}.json"

    if not os.path.exists(file_path):
        return {"error": "No stored data for this prefix"}

    with open(file_path, "r") as f:
        stored = json.load(f)

    matches = []
    for reg, name in stored["records"].items():
        if name_query in name:
            matches.append({"reg_no": reg, "name": name})

    return {"matches": matches}


# ================= PROGRESS =================
@app.get("/progress")
async def progress():
    return JSONResponse(state)


# ================= CONTROL =================
@app.post("/pause")
async def pause():
    state["paused"] = True
    return {"status": "paused"}


@app.post("/resume")
async def resume():
    state["paused"] = False
    return {"status": "resumed"}


@app.post("/stop")
async def stop():
    state["stop"] = True
    state["running"] = False
    return {"status": "stopped"}
