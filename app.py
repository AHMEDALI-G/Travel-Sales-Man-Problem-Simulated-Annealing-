from flask import Flask, jsonify, request
from flask_cors import CORS
import math
import random
import threading
import time

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

cities       = []
START_IDX    = 0
user_path    = []
current_path = []
best_path    = []
best_cost    = float('inf')
temperature  = 100.0
COOLING      = 0.995
MIN_TEMP     = 0.1
is_running   = False
timer_thread = None

def calculate_distance(path):
    if len(path) < 2:
        return 0
    total = 0
    for i in range(len(path) - 1):
        a = cities[path[i]]
        b = cities[path[i + 1]]
        total += math.hypot(a['x'] - b['x'], a['y'] - b['y'])
    if len(path) == len(cities):
        last  = cities[path[-1]]
        start = cities[START_IDX]
        total += math.hypot(last['x'] - start['x'], last['y'] - start['y'])
    return total

def clean_user_path():
    global user_path
    if not cities:
        return
    if not user_path:
        user_path = [START_IDX]
    if user_path[0] != START_IDX:
        user_path = [START_IDX] + [c for c in user_path if c != START_IDX]
    seen, result = set(), []
    for c in user_path:
        if c not in seen:
            seen.add(c)
            result.append(c)
    user_path = result

def generate_random_cities():
    return [{'x': random.random()*880+60, 'y': random.random()*480+50,
             'emoji': '🏡' if i == 0 else '🏘️'} for i in range(8)]

def reset_all():
    global cities, START_IDX, user_path, current_path, best_path, best_cost, temperature
    stop_algorithm()
    cities = generate_random_cities()
    START_IDX = 0
    user_path = [START_IDX]
    current_path = []
    best_path = []
    best_cost = float('inf')
    temperature = 100.0
    clean_user_path()
#algorithm
def make_neighbour(path):
     # Swap two random cities 
    if len(path) <= 2:
        return path[:]
    new_path    = path[:]
    i           = random.randint(1, len(path) - 1)
    j           = random.randint(1, len(path) - 1)
    new_path[i], new_path[j] = new_path[j], new_path[i]
    return new_path

def run_one_step():
    global current_path, best_path, best_cost, temperature

    if not is_running:
        return

    if len(current_path) != len(cities):
        current_path = user_path[:]

    # STEP 1 → make a neighbour by swapping 2 cities
    neighbour = make_neighbour(current_path)

    # STEP 2 → measure distances
    old_dist  = calculate_distance(current_path)
    new_dist  = calculate_distance(neighbour)

    # STEP 3 → accept or reject
    if new_dist < old_dist:
        current_path = neighbour                          # shorter → always accept
    else:
        probability = math.exp(-(new_dist - old_dist) / temperature)
        if random.random() < probability:
            current_path = neighbour                      # longer  → accept by chance

    # STEP 4 → save if this is the best path ever
    if calculate_distance(current_path) < best_cost:
        best_cost = calculate_distance(current_path)
        best_path = current_path[:]

    # STEP 5 → cool down temperature
    temperature = max(MIN_TEMP, temperature * COOLING)

def annealing_loop():
    while is_running:
        run_one_step()
        time.sleep(0.03)       

def start_algorithm():
    global is_running, timer_thread
    if is_running:
        return
    is_running   = True
    timer_thread = threading.Thread(target=annealing_loop, daemon=True)
    timer_thread.start()

def stop_algorithm():
    global is_running
    is_running = False
#routes
@app.route('/')
def serve_homepage():
    return app.send_static_file('index.html')

@app.route('/api/state', methods=['GET'])
def get_state():
    return jsonify({
        'cities':    cities,
        'userPath':  user_path,
        'bestPath':  best_path,
        'bestCost':  best_cost if best_cost != float('inf') else None,
        'T':         temperature,
        'isRunning': is_running
    })

@app.route('/api/reset', methods=['POST'])
def api_reset():
    reset_all()
    return jsonify({'success': True})

@app.route('/api/custom/start', methods=['POST'])
def start_custom_mode():
    global cities, user_path, best_path, best_cost
    stop_algorithm()
    cities = []; user_path = []; best_path = []; best_cost = float('inf')
    return jsonify({'success': True})

@app.route('/api/custom/add-node', methods=['POST'])
def add_city():
    global cities, user_path
    data  = request.get_json()
    index = len(cities)
    cities.append({'x': data.get('x'), 'y': data.get('y'),
                   'emoji': '🏡' if index == 0 else data.get('emoji', '🏘️')})
    user_path = [START_IDX]
    clean_user_path()
    return jsonify({'success': True})

@app.route('/api/update-user-path', methods=['POST'])
def update_user_path():
    global user_path
    user_path = request.get_json().get('path', [])
    clean_user_path()
    return jsonify({'success': True})

@app.route('/api/run-annealing/start', methods=['POST'])
def api_start_annealing():
    global user_path, current_path, best_cost, best_path
    if len(cities) < 2:
        return jsonify({'error': 'Need at least 2 cities'}), 400
    if len(user_path) != len(cities):
        user_path = [START_IDX] + [i for i in range(len(cities)) if i != START_IDX]
        clean_user_path()
    current_path = user_path[:]
    if best_cost == float('inf'):
        best_cost = calculate_distance(current_path)
        best_path = current_path[:]
    start_algorithm()
    return jsonify({'success': True})

@app.route('/api/run-annealing/stop', methods=['POST'])
def api_stop_annealing():
    stop_algorithm()
    return jsonify({'success': True})
#server
if __name__ == '__main__':
    reset_all()
    print("Server running → open http://localhost:3000")
    app.run(port=3000, debug=False)