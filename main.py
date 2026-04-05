from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "NBA Data Pipeline is running"}