import os
import glob
import shutil
import subprocess
import threading
from emitjudge import SocketClient
from werkzeug.utils import secure_filename
from collections import deque
from utils import compileFile

class Hub:
    '''
    Class to run the submissions fed by the judge server and notify the backend when judging is finished 
    via a socket connection
    '''
    def __init__(self, judge_cnt, judge_dir, p1_file_dir, p2_file_dir, judge_file_dir, log_dir, result_dir, socket_server_url):
        self.judges = []
        self.problems = [] 
        
        # Number of judge. 
        self.judgeCnt = judge_cnt
        
        # Directories to store temporary files when running submissions
        self.judgeDir = judge_dir
        
        # Directories to store submissions' files
        self.p1FileDir = p1_file_dir
        self.p2FileDir = p2_file_dir
        self.judgeFileDir = judge_file_dir
        
        # Directories to store result files
        self.logDir = log_dir
        self.resultDir = result_dir
        
        # Submission queue
        self.submission_queue = deque()
        
        self.socket_server_url = socket_server_url
        self.socket_client = None
        
        # A thread that listen to incoming submissions and run them. 
        self.consuming_thread = None
        
        # A scaffold directory with necessary files and directories to run a submission. 
        sDir = os.path.join(judge_dir, 'scaffold')
        
        # Clone the scaffold directory. The judges will populated these clones with submissions' files. 
        for i in range(judge_cnt):
            jDir = os.path.join(judge_dir, f'judge{i}')  
            shutil.copytree(sDir, jDir, dirs_exist_ok=True)
            self.judges.append(Judge(jDir, self.logDir, self.resultDir, self))

    def connectToSocketServer(self): 
        self.socket_client = SocketClient(self.socket_server_url)

    def clearJudges(self, judge_cnt = None, judge_dir = None):
        '''
        Method to remove the cloned directories that the judges used
        before the Hub is destroyed
        '''
        
        if judge_cnt is None:
            judge_cnt = self.judgeCnt
            judge_dir = self.judgeDir
        for i in range(judge_cnt):
            jDir = os.path.join(judge_dir, f'judge{i}') 
            if os.path.isdir(jDir): 
                shutil.rmtree(jDir)

    def __del__(self):
        self.clearJudges()

    def addSubmission(self, player1_file, player2_file, judge_file, submission_id):
        '''
        Method to handle submissions fed by the server. 
        '''
        # Save the submissions' file into corrresponding directories
        player1_file.save(os.path.join(self.p1FileDir, f'{submission_id}.{player1_file.filename.split(".")[-1]}'))
        player2_file.save(os.path.join(self.p2FileDir, f'{submission_id}.{player2_file.filename.split(".")[-1]}'))
        judge_file.save(os.path.join(self.judgeFileDir, f'{submission_id}.{judge_file.filename.split(".")[-1]}'))
        
        # Add the submission to the queue. consumer_thread will always look for the next submission from this queue
        # to run. 
        self.submission_queue.append(submission_id)

    def startConsumingSubmissions(self): 
        '''
        Method to set up a thread to listen to and run new submissions 
        from the server. 
        '''
        if self.consuming_thread is not None:
            raise Exception("Hub already started listening")
        
        self.consuming_thread = threading.Thread(target=self.runSubmissionsLoop)
        self.consuming_thread.start()

    def runSubmissionsLoop(self): 
        # Keep looking for new submissions to run. 
        while(True):
            if(self.submission_queue):  
                self.runNextSubmission()

    def runNextSubmission(self):
        '''
        Method to run the next submission and attempt to notify the backend when judging is finished. 
        If submission_queue is empty, raise an exception.
        '''
        if not self.submission_queue: 
            raise Exception("Attempting to run the next submission when the queue is empty")
        
        for judge in self.judges:
            if not judge.isOccupied:
                # Get the id of the next submission
                submission_id = self.submission_queue.popleft()
                
                judge.markAsOccupied()
                
                # Load the submissions' file from the corresponding directories into 
                # a clone of the scaffold directory
                player1_file = glob.glob(os.path.join(self.p1FileDir, f'{submission_id}.*'))[0]
                player2_file = glob.glob(os.path.join(self.p2FileDir, f'{submission_id}.*'))[0]
                judge_file = glob.glob(os.path.join(self.judgeFileDir, f'{submission_id}.*'))[0]
                judge.saveFiles(player1_file, player2_file, judge_file, submission_id)
                
                # Run the submission
                judge.runAndMarkAsUnoccupied()
                
                # Attempt to notify the backend if it is online
                if self.socket_client is None:  
                    print("Warning: not connected to socket server. Failed to notify about finishing judge")
                else: 
                    try: 
                        self.socket_client.finishJudge(submission_id)
                    except Exception as err: 
                        print("Notififying socket server of finishing judge met with exception: ")
                        print(err)
                
                break 
    
class Judge:
    ''' 
    Class for running submissions. 
    Each judge has a corresponding clone of the scaffold directory
    as its working directory. 
    '''
    def __init__(self, judge_dir, log_dir, resultDir, hub):
        self.hub = hub
        
        # Directory to store the log files
        self.logDir = log_dir
        
        # Directory to store the result files
        self.resultDir = resultDir
        
        self.isOccupied = False
        
        # The working directory for this judge
        self.folderPath = judge_dir

    def markAsOccupied(self):
        self.isOccupied = True

    def markAsUnoccupied(self):
        self.isOccupied = False

    def saveFiles(self, player1_filepath, player2_filepath, judge_file_path, submission_id):
        '''
        Method to compile the submissions' files and populating the resulting executable 
        into the working directory. Remove the source files after compiling them. 
        '''
        
        compileFile(player1_filepath, f'{self.folderPath}/p1root/player1')
        compileFile(player2_filepath, f'{self.folderPath}/p2root/player2')
        compileFile(judge_file_path, f'{self.folderPath}/judge')
        
        # Remove the source files
        os.remove(player1_filepath)
        os.remove(player2_filepath)
        os.remove(judge_file_path)
        
        self.subId = submission_id

    def runAndMarkAsUnoccupied(self):
        '''
        Method to run the submission
        '''
        
        print(f"Compiling submission #{self.subId} on thread# {threading.get_ident()}", flush=True)
        compileFile(f'{self.folderPath}/gameMaster.cpp', f'{self.folderPath}/gameMaster')

        print(f"Running submission #{self.subId} on thread# {threading.get_ident()}", flush=True)
        subprocess.run(['./gameMaster'], cwd=self.folderPath)
        
        # Copy the result files to their corresponding directories
        shutil.copy(f'{self.folderPath}/log.txt', f'{self.logDir}/{self.subId}.txt')
        shutil.copy(f'{self.folderPath}/result.json', f'{self.resultDir}/{self.subId}.json')
        
        print(f"Finished running submission #{self.subId} on thread# {threading.get_ident()}", flush=True)
        self.markAsUnoccupied()