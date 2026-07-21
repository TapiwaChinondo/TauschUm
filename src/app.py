from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Testing fast API Welcome to TauschUm!"}


@app.get("/items")
def get_items():
    return [
        {
            "name": "Xbox",
            "owner": "Tapi"
        },
        {
            "name": "TV",
            "owner": "Dish"
        }
    ]
    
@app.get("/math")    
def get_math():
    num = 1
    return [
        num +10
    ]