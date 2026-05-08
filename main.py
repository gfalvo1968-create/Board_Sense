from ecosystem import get_ecosystem
@app.get("/ecosystem")
def ecosystem_data():
    return get_ecosystem()
