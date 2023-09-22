import subprocess
import os

def compileFile(src, dest):
    ''' 
    Function to compile a file with and save the executable
    Args: 
        src: path to the source file (must be c++ or python)
        dest: path to store the executable
    '''
    file_ext = src.split(".")[-1]
    if file_ext == "cpp":
        subprocess.run(["g++", "-std=c++17", src, "-o", dest])
    elif file_ext == "py":
        subprocess.run(["pyinstaller", "--onefile", "--distpath", os.path.dirname(dest), "--name", os.path.basename(dest), src])