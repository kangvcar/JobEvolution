from fastapi import FastAPI

app = FastAPI()

DOMAINS = [
    {"id": "ai", "name": "人工智能"},
    {"id": "data", "name": "大数据"},
    {"id": "system", "name": "智能系统"},
    {"id": "iot", "name": "物联网"},
]


@app.get("/meta")
def meta():
    return {"domains": DOMAINS}
