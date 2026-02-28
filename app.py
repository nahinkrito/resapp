from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import asyncio
import httpx
import re

app = FastAPI()
templates = Jinja2Templates(directory="templates")

BASE_URL = "https://rvrjcce.ac.in/examcell/results/regnoresultsR1.php"

# Global State (simple in-memory control)
state = {
    "running": False,
    "paused": False,
    "stop": False,
    "current": "",
    "checked": 0,
    "total": 0,
    "matches": [],
}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/start")
async def start_scan(data: dict):
    state.update({
        "running": True,
        "paused": False,
        "stop": False,
        "checked": 0,
        "matches": []
    })

    prefixes = data["prefixes"]
    start = int(data["start"])
    end = int(data["end"])
    delay = float(data["delay"])
    target_name = data["target_name"].upper()

    state["total"] = len(prefixes) * (end - start + 1)

    asyncio.create_task(scan(prefixes, start, end, delay, target_name))
    return {"status": "started"}


async def scan(prefixes, start, end, delay, target_name):
    async with httpx.AsyncClient() as client:
        for prefix in prefixes:
            for i in range(start, end + 1):

                if state["stop"]:
                    state["running"] = False
                    return

                while state["paused"]:
                    await asyncio.sleep(0.5)

                reg_no = f"{prefix}{i:03d}"
                state["current"] = reg_no

                try:
                    r = await client.get(BASE_URL, params={"q": reg_no})
                    html = r.text

                    match = re.search(r"Name\s*:\s*<b>(.*?)</b>", html)
                    if match:
                        name = match.group(1).strip().upper()
                        if target_name in name:
                            state["matches"].append({
                                "reg_no": reg_no,
                                "name": name
                            })

                except:
                    pass

                state["checked"] += 1
                await asyncio.sleep(delay)

        state["running"] = False


@app.get("/progress")
async def progress():
    return JSONResponse(state)


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
