import os
import sys
import json
import urllib.request
import tarfile
import zipfile
import subprocess
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QProgressBar, QApplication, QPushButton, QLineEdit, QFileDialog, QCheckBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt

def get_settings_path():
    appdata = os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA"))
    if not appdata:
        appdata = os.path.expanduser("~")
    base_dir = os.path.join(appdata, "VerilogStudio")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "settings.json")

def load_settings():
    path = get_settings_path()
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_settings(settings):
    path = get_settings_path()
    with open(path, 'w') as f:
        json.dump(settings, f)

def get_tools_dir():
    settings = load_settings()
    if "tools_dir" in settings and settings["tools_dir"]:
        return settings["tools_dir"]
    
    # Default
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

def create_desktop_shortcut():
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_path = os.path.join(desktop, "Verilog Studio.lnk")
        
        # Get path to current executable
        if getattr(sys, 'frozen', False):
            target = sys.executable
        else:
            target = os.path.abspath(sys.argv[0])
            
        vbs_script = os.path.join(os.environ.get('TEMP', ''), 'create_shortcut.vbs')
        with open(vbs_script, 'w') as f:
            f.write(f'''
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{target}"
oLink.Save
''')
        subprocess.run(['cscript', '//nologo', vbs_script], creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        print("Failed to create shortcut:", e)

class DownloaderThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, tools_dir):
        super().__init__()
        self.tools_dir = tools_dir
        
    def run(self):
        try:
            os.makedirs(self.tools_dir, exist_ok=True)
            
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
            if os.path.exists(tgz_path):
                os.remove(tgz_path)
            
            node_ver = "v20.11.1"
            node_url = f"https://nodejs.org/dist/{node_ver}/node-{node_ver}-win-x64.zip"
            node_zip = os.path.join(self.tools_dir, "node.zip")
            
            self.progress.emit(70, "Downloading Node.js...")
            self.download_file(node_url, node_zip, 70, 85)
            
            self.progress.emit(85, "Extracting Node.js...")
            with zipfile.ZipFile(node_zip, 'r') as zip_ref:
                zip_ref.extractall(self.tools_dir)
            if os.path.exists(node_zip):
                os.remove(node_zip)
            
            node_extract_dir = os.path.join(self.tools_dir, f"node-{node_ver}-win-x64")
            node_target_dir = os.path.join(self.tools_dir, "node")
            if os.path.exists(node_target_dir):
                import shutil
                shutil.rmtree(node_target_dir)
            os.rename(node_extract_dir, node_target_dir)
            
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
            chunk_size = 1024 * 1024
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
    def __init__(self, default_tools_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verilog Studio Setup")
        self.setFixedSize(500, 220)
        
        layout = QVBoxLayout()
        
        self.label = QLabel("Welcome to Verilog Studio! Before we start, we need to download the required open-source toolchain (Yosys, Iverilog, Node.js).")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        
        # Path selection
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setText(default_tools_dir)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(QLabel("Install path:"))
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)
        
        # Desktop shortcut
        self.shortcut_checkbox = QCheckBox("Create Desktop Shortcut")
        self.shortcut_checkbox.setChecked(True)
        layout.addWidget(self.shortcut_checkbox)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        self.install_btn = QPushButton("Install Tools")
        self.install_btn.clicked.connect(self.start_install)
        layout.addWidget(self.install_btn)
        
        self.setLayout(layout)
        
    def browse_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Install Directory", self.path_input.text())
        if dir_path:
            self.path_input.setText(dir_path)
            
    def start_install(self):
        tools_dir = self.path_input.text().strip()
        
        # Save settings
        settings = load_settings()
        settings["tools_dir"] = tools_dir
        save_settings(settings)
        
        self.path_input.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.install_btn.setEnabled(False)
        self.shortcut_checkbox.setEnabled(False)
        
        self.thread = DownloaderThread(tools_dir)
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()
        
    def update_progress(self, val, text):
        self.progress_bar.setValue(val)
        self.label.setText(text)
        
    def on_finished(self, success, msg):
        if success:
            if self.shortcut_checkbox.isChecked():
                create_desktop_shortcut()
            self.accept()
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to download tools: {msg}")
            self.path_input.setEnabled(True)
            self.browse_btn.setEnabled(True)
            self.install_btn.setEnabled(True)
            self.shortcut_checkbox.setEnabled(True)
