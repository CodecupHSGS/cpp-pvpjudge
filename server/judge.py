import os
import glob
import shutil
import subprocess
from emitjudge import SocketClient
from werkzeug.utils import secure_filename
from collections import deque
from utils import compileFile

class Hub:

    def __init__(self, judge_cnt, judge_dir, p1_file_dir, p2_file_dir, judge_file_dir, log_dir, result_dir, socket_url):
        self.judges = []
        self.problems = [] 
        self.judgeCnt = judge_cnt
        self.judgeDir = judge_dir
        self.p1FileDir = p1_file_dir
        self.p2FileDir = p2_file_dir
        self.judgeFileDir = judge_file_dir
        self.logDir = log_dir
        self.resultDir = result_dir
        self.submission_queue = deque()
        
        self.socket_url = socket_url
        self.socket_client = None
        
        sDir = os.path.join(judge_dir, 'scaffold')
        for i in range(judge_cnt):
            jDir = os.path.join(judge_dir, f'judge{i}')  
            shutil.copytree(sDir, jDir, dirs_exist_ok=True)
            self.judges.append(Judge(jDir, self.logDir, self.resultDir, self))

    def connectToSocketServer(self): 
        self.socket_client = SocketClient(self.socket_url)
    
    def judgeComplete(self, judge):
        if self.submission_queue:
            self.runNextSubmission()

    def clearJudges(self, judge_cnt = None, judge_dir = None):
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
        player1_file.save(os.path.join(self.p1FileDir, f'{submission_id}.{player1_file.filename.split(".")[-1]}'))
        player2_file.save(os.path.join(self.p2FileDir, f'{submission_id}.{player2_file.filename.split(".")[-1]}'))
        judge_file.save(os.path.join(self.judgeFileDir, f'{submission_id}.{judge_file.filename.split(".")[-1]}'))
        self.submission_queue.append(submission_id)
        self.runNextSubmission()

    def runNextSubmission(self):
        for judge in self.judges:
            if not judge.isOccupied:
                if self.submission_queue:
                    submission_id = self.submission_queue.popleft()
                    judge.markAsOccupied()
                    player1_file = glob.glob(os.path.join(self.p1FileDir, f'{submission_id}.*'))[0]
                    player2_file = glob.glob(os.path.join(self.p2FileDir, f'{submission_id}.*'))[0]
                    judge_file = glob.glob(os.path.join(self.judgeFileDir, f'{submission_id}.*'))[0]
                    judge.saveFiles(player1_file, player2_file, judge_file, submission_id)
                    judge.runAndMarkAsUnoccupied()
                    
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
    def __init__(self, judge_dir, log_dir, resultDir, hub):
        self.hub = hub
        self.logDir = log_dir
        self.resultDir = resultDir
        self.isOccupied = False
        self.folderPath = judge_dir

    def markAsOccupied(self):
        self.isOccupied = True

    def markAsUnoccupied(self):
        self.isOccupied = False
        self.hub.judgeComplete(self)

    def saveFiles(self, player1_filepath, player2_filepath, judge_file_path, submission_id):
        compileFile(player1_filepath, f'{self.folderPath}/p1root/player1')
        compileFile(player2_filepath, f'{self.folderPath}/p2root/player2')
        compileFile(judge_file_path, f'{self.folderPath}/judge')
        self.subId = submission_id

    def runAndMarkAsUnoccupied(self):
        compileFile(f'{self.folderPath}/gameMaster.cpp', f'{self.folderPath}/gameMaster')

        subprocess.run(['./gameMaster'], cwd=self.folderPath)
        shutil.copy(f'{self.folderPath}/log.txt', f'{self.logDir}/{self.subId}.txt')
        shutil.copy(f'{self.folderPath}/result.json', f'{self.resultDir}/{self.subId}.json')
        self.markAsUnoccupied()