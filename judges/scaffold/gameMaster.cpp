#include <iostream>
#include <fstream>
#include <string>
#include <cstdio>
#include <chrono>
#include <dirent.h>
#include <unistd.h>
#include <poll.h>
#include <sstream>
#include <sandbox.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <format>
// not available on OS X, because why would it
#ifndef __APPLE__
#include <seccomp.h>
#endif

using namespace std;

class exFile {
    enum Languages {
        py, cpp, c, java, go, ruby, js
    };

    char buffer[1024];
    int toFile[2], fromFile[2];
    int cpuTime, ramMb;
    int timeLeft, lastResume;
    bool restricted;
    pid_t childId;

public:

    exFile(bool _restricted = true, int _timeLeft = INT32_MAX) : cpuTime(1), ramMb(64), timeLeft(_timeLeft), lastResume(-1),  restricted(_restricted) {
        buffer[0]='\0';
    }

    void runFile(string fileName, string fileRoot = "") {
        
        pid_t pid;

        if (pipe(toFile) == -1) {
            cerr << "Error: Failed to create pipe from main to file " << fileName << endl;
            exit(1);
        }
        if (pipe(fromFile) == -1) {
            cerr << "Error: Failed to create pipe from file " << fileName << " to main" <<endl;
            exit(1);
        }

        pid = fork();
        if (pid == -1) {
            cerr << "Error: Failed to create child process for file " << fileName << endl;
            exit(1);
        } else if (pid == 0) {
            // child process (File)
            
            // pipe from main
            {
                // close write end of the pipe
                close(toFile[1]);
                // redirect stdin to read end of the pipe
                dup2(toFile[0], STDIN_FILENO);
            }

            // pipe to main
            {
                // close write end of the pipe
                close(fromFile[0]);
                // redirect stdout to the write end of the pipe
                dup2(fromFile[1], STDOUT_FILENO);
            }

            if(restricted) {
                setRestriction(fileRoot);
            }

            // execute file
            cerr << ("./" + fileName).c_str() << endl; 
            execl(("./" + fileName).c_str(), ("./" + fileName).c_str(), NULL);
            perror("execl");

            // cant execute
            cerr << "Error: Failed to execute file " << fileName << endl;

            exit(1);
        } else {
            // parent process (main)
            // cerr << pid << " opened"<<endl;

            childId = pid;

            // close unneeded pipes:
            close(toFile[0]);
            close(fromFile[1]);
        }
    }

    void setResource(int _cpuTime, int _ramMb, int _timeLimit) {
        timeLeft = _timeLimit;
        cpuTime = _cpuTime;
        ramMb = _ramMb;
    }

    bool readLine(string &s) {
        static char buffer[1024];
        s = "";
        
        while (true) {
            if (strlen(buffer) == 0) {
                ssize_t n = read(fromFile[0], buffer, sizeof(buffer) - 1);
                if (n == 0) return false; // EOF reached
                buffer[n] = '\0';
            }
            
            s += buffer;
            size_t pos = s.find('\n');
            
            if (pos != string::npos) {
                // store remaining suffix in the buffer
                strncpy(buffer, &s[pos + 1], s.size() - pos - 1);
                buffer[s.size() - pos - 1] = '\0';
                
                // remove the suffix after the endl from s
                s.erase(pos + 1);
                break;
            } else {
                buffer[0] = '\0';
            }
        }
        cerr << "from " << childId << "line read: '" << s << "'" << endl;
        return true;
    }

    bool readLine(stringstream &strin) {
        string s = "";
        strin.str(""); // don't ask me why
        strin.clear(); // this is needed.
        if(readLine(s)) {
            strin.str(s);
            return true;
        }
        return false;
    }

    void writeLine(string &s) {
        cerr << "wrote '" << s << "' to " << childId << endl;
        if(write(toFile[1], s.c_str(), s.size()) == -1) {
            perror("write");
        }
    }

    void splitTime() {
        if(lastResume == -1) {
            return;
        }
        timeLeft -= max(0, getTime() - lastResume);
        lastResume = -1;
    }

    void resumeTime() {
        lastResume = getTime();
    }

    bool ensureInput(int timeout = -1) {
        pollfd pfd = {fromFile[0], POLLIN, 0};
        int timeoutMs = timeLeft;

        if(timeout != -1) timeoutMs = timeout;

        int ret = poll(&pfd, 1, timeoutMs);

        if (ret == -1) {
            perror("Poll");
            return 0;
        } else if (ret == 0) {
            cerr << "timeout" << endl;
            return 0;
        } else {
            return 1;
        }
    }

    int waitFile() {
        int status;
        waitpid(childId, &status, 0);
        return status;
    }

    void killProcess() {
        kill(childId, SIGTERM);
    }

    int getTimeLeft() {
        return timeLeft;
    }

private:

    int getTime() {
        return chrono::duration_cast<chrono::milliseconds>(chrono::system_clock::now().time_since_epoch()).count();
    }

    void setRestriction(string fileRoot) {
        struct rlimit limit;

        // limit cpu time
        limit.rlim_cur = (cpuTime - 1) / 1000 + 3;
        limit.rlim_max = (cpuTime - 1) / 1000 + 3;
        if (setrlimit(RLIMIT_CPU, &limit) < 0) {
            cerr << "limit cpu time failed for " << getpid() << endl;
            exit(1);
        }

        // limit mem usage (this is really getting on my nerves now https://developer.apple.com/forums/thread/702803)
        #ifndef __APPLE__
        limit.rlim_cur = 1ll * ramMb * 1024 * 1024;
        limit.rlim_max = 1ll * ramMb * 1024 * 1024;
        if (setrlimit(RLIMIT_AS, &limit) < 0) {
            cerr << "limit ram failed for " << getpid() << endl;
            exit(1);
        }
        #endif

        // sandbox process file access
        #ifndef __APPLE__
        if (system("unshare -m -p --fork --mount-proc chroot p1root ./player1") == -1) {
            cerr << "i cant even test this" << endl;
            exit(EXIT_FAILURE);
        }
        chdir("/");
        // chroot(fileRoot.c_str());
        #endif

        #ifdef __APPLE__
        if (chdir(fileRoot.c_str()) < 0) {
            cerr << "chdir failed" << endl;
            exit(1);
        }

        // struct rlimit noFileLimit; 
        // noFileLimit.rlim_cur = 0;
        // noFileLimit.rlim_max = 0;
        // if (setrlimit(RLIMIT_NOFILE, &noFileLimit) < 0) {
        //     cerr << "sandboxing failed for " << getpid() << endl;
        //     exit(1);
        // }

        // const char *sandbox_profile = "(version 1)(deny default)(allow file-write* (subpath \".\"))";

        // char *errorbuf;
        // int result = sandbox_init(sandbox_profile, SANDBOX_NAMED, &errorbuf);
        // if (result != 0) {
        //     std::cerr << "sandbox_init failed: " << errorbuf << '\n';
        //     sandbox_free_error(errorbuf);
        //     exit(1);
        // }
        #endif

        ofstream fout("playerlog.txt", ofstream::out);
        fout<<"player " << fileRoot << "joined on process " << getpid() << endl;

        //kill syscalls
        #ifndef __APPLE__
        scmp_filter_ctx ctx;
        ctx = seccomp_init(SCMP_ACT_ALLOW);
        seccomp_rule_add(ctx, SCMP_ACT_KILL, SCMP_SYS(execve), 0);
        seccomp_rule_add(ctx, SCMP_ACT_KILL, SCMP_SYS(socket), 0);
        seccomp_load(ctx);
        #endif
    }
};

class game {
    string pFiles[2], jFile;
    string pRoots[2];
    exFile *players[2], *judge;
    stringstream playerin, judgein;
    int curPlayer, curTurn;

public:

    enum TurnResult {
        win, lose, draw, valid, timeout, invalid
    };

    game(string _pFiles[], string _pRoots[], string _jFile) : curPlayer(0), curTurn(-1) {
        jFile = _jFile;
        judge = new exFile(false);
        for(int i = 0; i <= 1; i++) {
            pFiles[i] = _pFiles[i];
            pRoots[i] = _pRoots[i];
            players[i] = new exFile(true);
        }        
    }

    ~game() {
        delete judge;
        delete players[0]; delete players[1];
    }

    void prepGame() {
        string type;
        int _timeLimit;

        judge->runFile(jFile);

        // get time limit
        judge->readLine(judgein);
        judgein >> type; 

        cerr << type << endl; 

        assert(type=="time"); 
        judgein >> _timeLimit;
        
        for(int i = 0; i <= 1; i++) {
            players[i]->setResource(10 * _timeLimit, 64, _timeLimit);
        }

        curPlayer = 0;
    }

    void startGame() {
        for(int i = 0; i <= 1; i++) {
            string playerId = {(char)('1' + i), '\n'};
            players[i]->runFile(pFiles[i], pRoots[i]);
            cerr<<playerId;
            players[i]->writeLine(playerId);
        }
    }

    TurnResult nextTurn() {
        TurnResult turnRes = execTurn(players[curPlayer]);
        curPlayer ^=1, curTurn++;
        return turnRes;
    }

    int getCurPlayer() {
        return curPlayer ^ 1;
    }

    void waitJudge() {
        judge->waitFile();
    }

    void killPlayerProcess() {
        for(int i = 0; i <= 1; i++) {
            players[i]->killProcess();
        }
    }

    int playerTime(int playerId) {
        return players[playerId]->getTimeLeft();
    }

private:

    TurnResult execTurn(exFile *player) {
        string type, line;
        int lineCnt;
        // cerr<<"BUT IT GOT HERE"<<endl;
        judge->readLine(judgein);
        judgein >> type; cerr << type<<endl; judgein >> lineCnt;
        // cerr<<lineCnt<<" lmao1"<<endl;
        player->resumeTime();

        for(int i = 1; i <= lineCnt; i++) {
            judge->readLine(line);
            player->writeLine(line);
        }

        if(!player->ensureInput()) {
            player->splitTime();
            return timeout;
        }
        if(!player->readLine(line)) {
            return invalid;
        }
        player->splitTime();

        // string s = ""; s += (char)(curPlayer + '1'); s += " 0\n";
        // judge->writeLine(s);
        judge->writeLine(line);

        judge->readLine(judgein);
        judgein >> type;
        
        if(type == "invalid") return invalid;
        if(type == "lose") return lose;
        if(type == "win") return win;
        if(type == "draw") return draw;
        return valid;
    }
};

int main() {
    string playersF[] = {"player1", "player2"}, judgeF = "judge";
    string playersRoot[] = {"./p1root/", "./p2root/"};
    game gameM(playersF, playersRoot, judgeF);
    gameM.prepGame();
    gameM.startGame();
    while(true) {
        game::TurnResult res = gameM.nextTurn();
        int winner = -1;
        string reason;
        switch(res){
            case game::TurnResult::draw:
                winner = 0; break;
            case game::TurnResult::win:
                winner = gameM.getCurPlayer() + 1; reason = "valid"; break;
            case game::TurnResult::lose:
                winner = gameM.getCurPlayer() ^ 1 + 1; reason = "valid"; break;
            case game::TurnResult::timeout:
                winner = gameM.getCurPlayer() ^ 1 + 1; reason = "timeout"; break;
            case game::TurnResult::invalid:
                winner = gameM.getCurPlayer() ^ 1 + 1; reason = "invalid"; break;
            default:
                break;
        }
        cerr << gameM.getCurPlayer() << " this turn is: " << winner << endl;
        if(winner != -1) {
            gameM.waitJudge();
            ofstream logout("log.txt", ofstream::app);
            ofstream resultout("result.json"); 
            logout <<"winner " << winner << " " << reason << endl;
            resultout << "\{\"winner\":" << winner << ", \"reason\":\"" << reason << "\"\}";
            break;
        }
    }
    gameM.killPlayerProcess();
}