from flask import Flask, request, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import threading
from judge import Hub
import os
from dotenv import load_dotenv
import time
import random
import json

# Load environment varaibles
load_dotenv()
app_port = int(os.getenv("APP_PORT"))
judge_cnt = int(os.getenv("JUDGE_COUNT"))
judge_dir = os.getenv("JUDGE_DIR")
judge_file_dir = os.getenv("JUDGE_FILE_DIR")
p1_file_dir = os.getenv("P1_FILE_DIR")
p2_file_dir = os.getenv("P2_FILE_DIR")
log_dir = os.getenv("LOG_DIR")
result_dir = os.getenv("RESULT_DIR")
socket_server_url = os.getenv("SOCKET_SERVER_URL")

# Create a new Flask instance
app = Flask(__name__)

# Create a new Hub, which runs submissions 
# fed by the server and uses socket to notify 
# the backend server when a submission is judged
hub = Hub(
    judge_cnt=judge_cnt,
    judge_dir=judge_dir,
    p1_file_dir=p1_file_dir,
    p2_file_dir=p2_file_dir,
    judge_file_dir=judge_file_dir,
    log_dir=log_dir,
    result_dir=result_dir, 
    socket_server_url=socket_server_url
)

# Attempt to connect to the backend's socket server. 
# If the backend is online, it should connect sucessfully. 
# Otherwise, the Hub will wait for the backend's notification 
# when the backend is online. 
print("Hub attempting to connect to socket server")
try: 
    hub.connectToSocketServer()
    print("Connected to the socket server")
except: 
    print("Failed to connect to the socket server when initializing hub")
    
# Create a new thread to run submissions 
hub.startConsumingSubmissions()

@app.route("/connect")
def connect(): 
    '''
    Endpoint to handle the backend's notification that it is online
    '''
    
    print("Received notification that the socket server is online")
    print("Attempting to connect to the socket server")
    
    # The Hub retries to connect to the backend's socket server. 
    try:  
        hub.connectToSocketServer()
        print("Connected to the socket server")
    except: 
        print("Failed to create socket connection after being notified")

@app.route('/submit', methods=['POST'])
def submit():
    '''
    Endpoint to handle a submission from the backend
    '''
    
    print("Received a new submission")
    
    # Get and validate the required files 
    print(f"Available files in submission: {request.files.keys()}")

    if 'player1' not in request.files or 'player2' not in request.files:
        print("Missing at least one player file in the submission")
        return {'message': 'Missing player file'}, 400

    p1File = request.files['player1']
    p2File = request.files['player2']
    judgeFile = request.files['judge']

    if not (p1File.filename.endswith('.cpp') or p2File.filename.endswith('.cpp') or judgeFile.filename.endswith('.cpp')):
        return 'All files must be .cpp files', 400

    # Generate a random submission ID to assign to this submission
    submission_id = str(random.randint(10000, 99999)) + time.strftime("%H%M%S")
    
    # Add the submission to the hub
    hub.addSubmission(p1File, p2File, judgeFile, submission_id)
    
    return {'message': 'Submission received.', 'submission_id': submission_id}, 200

@app.route('/result/<submissionId>', methods=['GET'])
def result(submissionId):
    '''
    Endpoint to handle the backend's request for the result of a specific submission
    If the result file does exist, load the result and return a JSON. 
    Otherwise, return a message for explanation
    '''
    
    result_file_path = os.path.join(hub.resultDir, f'{submissionId}.json')
    
    if os.path.exists(result_file_path):
        # load the file into memory
        with open(result_file_path, "r") as result_file: 
            result = json.load(result_file)
            
        # delete the file 
        os.remove(result_file_path)
        
        return jsonify({'result': result}), 200
    else:
        return jsonify({'message': "Result file not found"}), 400

@app.route('/log/<submissionId>', methods=['GET'])
def log(submissionId): 
    '''
    Endpoint to handle the backend's request for the log of a specific submission
    If the log file does exist, return the file. 
    Otherwise, return a message for explanation
    '''
    log_file_path = os.path.join(hub.logDir, f'{submissionId}.txt')
    
    if os.path.exists(log_file_path):           
        # os.getcwd() is appended before hub.logdir 
        # in case an user runs the app from outside server/     
        file = send_from_directory(os.path.join(os.getcwd(), hub.logDir), f'{submissionId}.txt')
        
        # delete the file after loading into memory
        os.remove(log_file_path)
        
        return file
    else:
        return jsonify({'message': "Log file not found"}), 400

if __name__ == '__main__':
    app.run(port=app_port, debug=True)
    