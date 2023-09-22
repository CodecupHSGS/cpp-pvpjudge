import socketio
import eventlet

class SocketClient:
    '''Wrapper class for socketio.Client()
    '''
    
    def __init__(self, socket_url):
        self.sio = socketio.Client()
        self.socket_url = socket_url
        self.connect()

    def connect(self):
        self.sio.connect(self.socket_url)
        print("Socket connected")

    def disconnect(self):
        self.sio.disconnect()
        print("Socket disconnected")

    def finishJudge(self, submission_id):
        print(f"Emitting the event of finishing judging #{submission_id} to the server",flush=True)
        self.sio.emit('finish_judge', submission_id)

if __name__ == "__main__":
    socket_url = "http://localhost:6969"
    socket_client = SocketClient(socket_url)

    submission_id = ""
    socket_client.finishJudge(submission_id)

    socket_client.disconnect()
