import json
from flask import Flask, request
from flask_cors import CORS

# initialize the flask app
app = Flask(__name__)
CORS(app)

if __name__ == '__main__':
    app.run(debug=True, port=5050)

@app.route('/')
def health_check():
    return "Server is running!"

@app.route('/real/<id>/<trikes_cnt>/<pass_cnt>')
def real_simulation(id, trikes_cnt, pass_cnt):
    """
    Make sure that this follows the same format as the Simulator so that
    the files can be found.
    """

    trikes = []
    passengers = []
    for i in range(int(trikes_cnt)):
        try:
            with open(f'data/real/{id}/trike_{i}.json') as f:
                trike = json.load(f)
                trikes.append(trike)
        except Exception:
            pass
    for i in range(int(pass_cnt)):
        try:
            with open(f'data/real/{id}/passenger_{i}.json') as f:
                passenger = json.load(f)
                passengers.append(passenger)
        except Exception:
            pass
    return {
        "trikes": trikes,
        "passengers": passengers
    }

@app.route('/real/<id>/terminals.json')
def terminals_data(id):
    """Serve all terminal data."""
    try:
        with open(f'data/real/{id}/terminals.json') as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}, 404

@app.route('/real/<id>/roam_endpoints.json')
def roam_endpoints(id):
    """Serve roam endpoints data."""
    try:
        with open(f'data/real/{id}/roam_endpoints.json') as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}, 404

@app.route('/real/<id>/metadata.json')
def metadata(id):
    """Serve metadata."""
    try:
        with open(f'data/real/{id}/metadata.json') as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}, 404

@app.route('/real/<id>/summary.json')
def summary(id):
    """Serve summary statistics."""
    try:
        with open(f'data/real/{id}/summary.json') as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}, 404