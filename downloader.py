import os
import sys
import json
import urllib.request
import tarfile
import zipfile
import subprocess
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QApplication
from PyQt5.QtCore import QThread, pyqtSignal, Qt

class DownloaderThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, tools_dir):
        super().__init__()
        self.tools_dir = tools_dir
        
    def run(self):
        try:
            os.makedirs(self.tools_dir, exist_ok=True)
            
            # 1. Download OSS CAD Suite
            self.progress.emit(0, "Fetching latest OSS CAD Suite info...")
            url = "https://api.github.com/repos/YosysHQ/oss-cad-suite-build/releases/latest"
            req = urllib.request.Request(url, headers={'User-Agent': 'VerilogStudio'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                
            tgz_url = None
            for asset in data.get('assets', []):
                if 'windows-x64' in asset['name'] and asset['name'].endswith('.tgz'):
                    tgz_url = asset['browser_download_url']
                    break
                    
            if not tgz_url:
                raise Exception("Could not find OSS CAD Suite for Windows.")
                
            tgz_path = os.path.join(self.tools_dir, "oss-cad-suite.tgz")
            self.progress.emit(10, "Downloading OSS CAD Suite (this may take a while)...")
            self.download_file(tgz_url, tgz_path, 10, 50)
            
            self.progress.emit(50, "Extracting OSS CAD Suite...")
            with tarfile.open(tgz_path, "r:gz") as tar:
                tar.extractall(path=self.tools_dir)
            os.remove(tgz_path)
            
            # 2. Download Node.js
            node_ver = "v20.11.1"
            node_url = f"https://nodejs.org/dist/{node_ver}/node-{node_ver}-win-x64.zip"
            node_zip = os.path.join(self.tools_dir, "node.zip")
            
            self.progress.emit(70, "Downloading Node.js...")
            self.download_file(node_url, node_zip, 70, 85)
            
            self.progress.emit(85, "Extracting Node.js...")
            with zipfile.ZipFile(node_zip, 'r') as zip_ref:
                zip_ref.extractall(self.tools_dir)
            os.remove(node_zip)
            
            # Rename node folder
            node_extract_dir = os.path.join(self.tools_dir, f"node-{node_ver}-win-x64")
            node_target_dir = os.path.join(self.tools_dir, "node")
            if os.path.exists(node_target_dir):
                import shutil
                shutil.rmtree(node_target_dir)
            os.rename(node_extract_dir, node_target_dir)
            
            # 3. Install netlistsvg locally
            self.progress.emit(90, "Installing netlistsvg...")
            npm_cmd = os.path.join(node_target_dir, "npm.cmd")
            env = os.environ.copy()
            env["PATH"] = f"{node_target_dir};" + env.get("PATH", "")
            subprocess.run([npm_cmd, "install", "-g", "netlistsvg"], env=env, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            self.progress.emit(100, "Setup complete!")
            self.finished.emit(True, "Success")
            
        except Exception as e:
            self.finished.emit(False, str(e))
            
    def download_file(self, url, dest, start_prog, end_prog):
        req = urllib.request.Request(url, headers={'User-Agent': 'VerilogStudio'})
        with urllib.request.urlopen(req) as response:
            total_size = int(response.info().get('Content-Length', 0))
            downloaded = 0
            chunk_size = 1024 * 1024 # 1MB chunks
            with open(dest, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        prog = start_prog + int((downloaded / total_size) * (end_prog - start_prog))
                        self.progress.emit(prog, f"Downloading... ({downloaded//1024//1024}MB / {total_size//1024//1024}MB)")

class DownloadDialog(QDialog):
    def __init__(self, tools_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Installing Toolchain")
        self.setFixedSize(400, 150)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        
        layout = QVBoxLayout()
        
        self.label = QLabel("Verilog Studio needs to download some tools (Yosys, Iverilog, Node.js).")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
        
        self.thread = DownloaderThread(tools_dir)
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.on_finished)
        
    def start(self):
        self.thread.start()
        
    def update_progress(self, val, text):
        self.progress_bar.setValue(val)
        self.label.setText(text)
        
    def on_finished(self, success, msg):
        if success:
            self.accept()
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to download tools: {msg}")
            self.reject()

def get_tools_dir():
    appdata = os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA"))
    if not appdata:
        appdata = os.path.expanduser("~")
    return os.path.join(appdata, "VerilogStudio", "tools")

def check_dependencies():
    tools_dir = get_tools_dir()
    yosys_path = os.path.join(tools_dir, "oss-cad-suite", "bin", "yosys.exe")
    node_path = os.path.join(tools_dir, "node", "node.exe")
    netlistsvg_path = os.path.join(tools_dir, "node", "netlistsvg.cmd")
    
    return os.path.exists(yosys_path) and os.path.exists(node_path) and os.path.exists(netlistsvg_path)

def get_env_paths():
    tools_dir = get_tools_dir()
    oss_bin = os.path.join(tools_dir, "oss-cad-suite", "bin")
    oss_lib = os.path.join(tools_dir, "oss-cad-suite", "lib")
    node_dir = os.path.join(tools_dir, "node")
    return f"{oss_bin};{oss_lib};{node_dir};"
