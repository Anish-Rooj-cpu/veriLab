import sys
import os
import subprocess
import webbrowser
import json
import glob
import shutil
from PyQt5.QtWidgets import (QApplication, QMainWindow, QAction, QFileDialog, 
                             QTabWidget, QDockWidget, QPlainTextEdit, QMessageBox,
                             QFileSystemModel, QTreeView, QVBoxLayout, QWidget, QSplitter,
                             QDialog, QPushButton, QLabel, QHBoxLayout, QStyle, QCompleter)
from PyQt5.QtCore import Qt, QProcess, QThread, pyqtSignal, QSize, QTimer, QStringListModel
from PyQt5.QtGui import QIcon, QFont, QImage, QPainter, QColor, QPixmap, QTextCursor
from PyQt5.QtSvg import QSvgRenderer

from code_editor import CodeEditor
from highlighter import VerilogHighlighter

class WorkerThread(QThread):
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, cmd, cwd):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd

    def run(self):
        try:
            env = os.environ.copy()
            oss_bin = r"C:\oss-cad-suite\bin"
            oss_lib = r"C:\oss-cad-suite\lib"
            graphviz_bin = r"C:\Program Files\Graphviz\bin"
            npm_global = os.path.join(os.environ.get("APPDATA", ""), "npm")
            env["PATH"] = f"{oss_bin};{oss_lib};{graphviz_bin};{npm_global};" + env.get("PATH", "")
            # Strip PyInstaller env vars that conflict with oss-cad-suite tools
            for key in list(env.keys()):
                if key in ("TCL_LIBRARY", "TK_LIBRARY") or key.startswith("QT_") or key.startswith("QML"):
                    del env[key]

            process = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, cwd=self.cwd, shell=True, env=env)
            for line in process.stdout:
                self.output_signal.emit(line.strip())
            process.wait()
            self.finished_signal.emit(process.returncode)
        except Exception as e:
            self.output_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(-1)

class StartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Verilog Studio")
        self.setFixedSize(450, 200)
        self.project_dir = None
        
        layout = QVBoxLayout()
        
        label = QLabel("Welcome to Verilog Studio!\nPlease open an existing project or create a new one.")
        label.setAlignment(Qt.AlignCenter)
        label.setFont(QFont("Segoe UI", 12))
        layout.addWidget(label)
        
        btn_layout = QHBoxLayout()
        
        btn_new = QPushButton("Create New Project")
        btn_new.setMinimumHeight(40)
        btn_new.clicked.connect(self.create_project)
        
        btn_open = QPushButton("Open Project")
        btn_open.setMinimumHeight(40)
        btn_open.clicked.connect(self.open_project)
        
        btn_layout.addWidget(btn_new)
        btn_layout.addWidget(btn_open)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def create_project(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Empty Directory for New Project")
        if dir_path:
            os.makedirs(os.path.join(dir_path, "sources"), exist_ok=True)
            os.makedirs(os.path.join(dir_path, "simulations"), exist_ok=True)
            os.makedirs(os.path.join(dir_path, "synthesis"), exist_ok=True)
            
            with open(os.path.join(dir_path, "project.vprj"), "w") as f:
                json.dump({"name": os.path.basename(dir_path)}, f)
            
            self.project_dir = dir_path
            self.accept()

    def open_project(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if dir_path:
            os.makedirs(os.path.join(dir_path, "sources"), exist_ok=True)
            os.makedirs(os.path.join(dir_path, "simulations"), exist_ok=True)
            os.makedirs(os.path.join(dir_path, "synthesis"), exist_ok=True)
            self.project_dir = dir_path
            self.accept()


class ClickableConsole(QPlainTextEdit):
    error_clicked = pyqtSignal(str, int) # filename, line_number

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        cursor = self.cursorForPosition(event.pos())
        line_text = cursor.block().text()
        
        import re
        # Match iverilog/yosys error lines like: dma_controller.v:45: syntax error
        match = re.search(r'([^\\/]+\.(?:v|sv)):(\d+):', line_text)
        if match:
            filename = match.group(1)
            line_num = int(match.group(2))
            self.error_clicked.emit(filename, line_num)

class MainWindow(QMainWindow):
    def __init__(self, project_dir):
        super().__init__()
        self.project_dir = project_dir
        self.project_name = os.path.basename(project_dir)
        
        self.setWindowTitle(f"Verilog Studio - {self.project_name}")
        self.resize(1200, 800)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True) # Cleaner UI for tabs
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)

        self.current_files = {} 
        
        self.init_ui()

    def init_ui(self):
        self.create_actions()
        self.create_menus()
        self.create_toolbars()
        self.create_dock_windows()

    def create_text_icon(self, text, bg_color):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.setBrush(QColor(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(2, 2, 28, 28, 6, 6)
        
        painter.setPen(Qt.white)
        font = QFont("Arial", 12, QFont.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, text)
        painter.end()
        
        return QIcon(pixmap)

    def create_actions(self):
        style = self.style()
        
        icon_new_design = self.create_text_icon("D*", "#2196F3") # Blue
        icon_new_sim = self.create_text_icon("S*", "#4CAF50") # Green
        icon_add_design = self.create_text_icon("+D", "#1976D2") # Dark Blue
        icon_add_sim = self.create_text_icon("+S", "#388E3C") # Dark Green
        
        self.new_design_act = QAction(icon_new_design, "New Design Source", self)
        self.new_design_act.triggered.connect(self.new_design_source)

        self.new_sim_act = QAction(icon_new_sim, "New Simulation Source", self)
        self.new_sim_act.triggered.connect(self.new_sim_source)
        
        self.add_design_act = QAction(icon_add_design, "Add Design Source...", self)
        self.add_design_act.triggered.connect(self.add_design_source)
        
        self.add_sim_act = QAction(icon_add_sim, "Add Simulation Source...", self)
        self.add_sim_act.triggered.connect(self.add_sim_source)

        self.save_act = QAction(style.standardIcon(QStyle.SP_DialogSaveButton), "Save", self)
        self.save_act.setShortcut("Ctrl+S")
        self.save_act.triggered.connect(self.save_file)

        self.exit_act = QAction("Exit", self)
        self.exit_act.triggered.connect(self.close)

        self.sim_act = QAction(style.standardIcon(QStyle.SP_MediaPlay), "Simulate (iverilog)", self)
        self.sim_act.setShortcut("F5")
        self.sim_act.triggered.connect(self.simulate)

        self.synth_act = QAction(style.standardIcon(QStyle.SP_CommandLink), "Synthesize (Yosys)", self)
        self.synth_act.setShortcut("F6")
        self.synth_act.triggered.connect(self.synthesize)

        self.wave_act = QAction(style.standardIcon(QStyle.SP_DesktopIcon), "View Waveform", self)
        self.wave_act.setShortcut("F7")
        self.wave_act.triggered.connect(self.view_waveform)

    def create_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction(self.new_design_act)
        file_menu.addAction(self.add_design_act)
        file_menu.addSeparator()
        file_menu.addAction(self.new_sim_act)
        file_menu.addAction(self.add_sim_act)
        file_menu.addSeparator()
        file_menu.addAction(self.save_act)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_act)

        run_menu = menubar.addMenu("Flow")
        run_menu.addAction(self.sim_act)
        run_menu.addAction(self.synth_act)
        run_menu.addAction(self.wave_act)

    def create_toolbars(self):
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(20, 20))
        toolbar.addAction(self.new_design_act)
        toolbar.addAction(self.new_sim_act)
        toolbar.addAction(self.save_act)
        toolbar.addSeparator()
        toolbar.addAction(self.add_design_act)
        toolbar.addAction(self.add_sim_act)
        toolbar.addSeparator()
        toolbar.addAction(self.sim_act)
        toolbar.addAction(self.synth_act)
        toolbar.addAction(self.wave_act)

    def create_dock_windows(self):
        self.console_dock = QDockWidget("Console Output", self)
        self.console_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.console = ClickableConsole()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 10))
        self.console.setStyleSheet("background-color: #FAFAFA; color: #111111; border: 1px solid #CCC;")
        self.console.error_clicked.connect(self.jump_to_error)
        self.console_dock.setWidget(self.console)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)

        self.explorer_dock = QDockWidget("Project Explorer", self)
        self.explorer_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(self.project_dir)
        
        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        self.tree.setRootIndex(self.file_model.index(self.project_dir))
        self.tree.doubleClicked.connect(self.tree_double_clicked)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setStyleSheet("background-color: #FFFFFF; color: #000000; border: none;")
        
        self.explorer_dock.setWidget(self.tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.explorer_dock)

    def tree_double_clicked(self, index):
        path = self.file_model.filePath(index)
        if os.path.isfile(path):
            self.load_file(path)

    def jump_to_error(self, filename, line_num):
        # Find the file in the project
        target_path = None
        for root, dirs, files in os.walk(self.project_dir):
            if filename in files:
                target_path = os.path.join(root, filename)
                break
                
        if target_path:
            self.load_file(target_path)
            # Find the tab we just opened/activated
            for i in range(self.tabs.count()):
                if self.current_files.get(i, {}).get("path") == target_path:
                    editor = self.tabs.widget(i)
                    block = editor.document().findBlockByNumber(line_num - 1)
                    if block.isValid():
                        cursor = editor.textCursor()
                        cursor.setPosition(block.position())
                        editor.setTextCursor(cursor)
                        editor.ensureCursorVisible()
                    break

    def create_editor(self, text="", title="Untitled"):
        editor = CodeEditor()
        editor.setPlainText(text)
        highlighter = VerilogHighlighter(editor.document())
        
        # 5. Code Autocomplete
        keywords = ["always", "assign", "begin", "case", "casex", "casez", "default", "defparam", "else", "end", "endcase", "endmodule", "if", "inout", "input", "module", "output", "parameter", "reg", "wire", "initial", "integer"]
        completer = QCompleter(keywords, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        editor.setCompleter(completer)
        
        # 1. Real-Time Syntax Checking
        timer = QTimer(editor)
        timer.setSingleShot(True)
        timer.setInterval(750) # 750ms after typing stops
        timer.timeout.connect(lambda: self.lint_code(editor))
        editor.textChanged.connect(timer.start)
        
        index = self.tabs.addTab(editor, title)
        self.tabs.setCurrentIndex(index)
        return index

    def lint_code(self, editor):
        # Only lint if we have Icarus Verilog in PATH or OSS CAD Suite
        text = editor.toPlainText()
        if not text.strip():
            editor.setErrors([])
            return
            
        import tempfile
        import re
        try:
            with tempfile.NamedTemporaryFile(suffix=".v", delete=False, mode="w", encoding="utf-8") as f:
                f.write(text)
                temp_name = f.name
                
            env = os.environ.copy()
            oss_bin = r"C:\oss-cad-suite\bin"
            env["PATH"] = f"{oss_bin};" + env.get("PATH", "")
            
            # Run iverilog syntax check only (-tnull)
            process = subprocess.Popen(f'iverilog -tnull "{temp_name}"', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True, env=env)
            out, _ = process.communicate()
            
            error_lines = []
            # iverilog error format: file.v:line: error: ...
            for line in out.splitlines():
                match = re.search(r':(\d+):\s*(error|syntax error)', line, re.IGNORECASE)
                if match:
                    line_num = int(match.group(1)) - 1 # 0-indexed for editor
                    error_lines.append(line_num)
            
            editor.setErrors(error_lines)
            os.remove(temp_name)
        except Exception as e:
            pass # Ignore lint errors if tools missing

    def close_tab(self, index):
        if index in self.current_files:
            del self.current_files[index]
        self.tabs.removeTab(index)

    def new_design_source(self):
        index = self.create_editor(title="Untitled_Design.v")
        self.current_files[index] = {"path": None, "type": "design"}

    def new_sim_source(self):
        index = self.create_editor(title="Untitled_Sim.v")
        self.current_files[index] = {"path": None, "type": "sim"}
        
    def add_design_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Add Design Source", "", "Verilog Files (*.v *.sv);;All Files (*.*)")
        if path:
            dest = os.path.join(self.project_dir, "sources", os.path.basename(path))
            shutil.copy(path, dest)
            self.log(f"Added design source: {dest}")
            self.load_file(dest)
            
    def add_sim_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Add Simulation Source", "", "Verilog Files (*.v *.sv);;All Files (*.*)")
        if path:
            dest = os.path.join(self.project_dir, "simulations", os.path.basename(path))
            shutil.copy(path, dest)
            self.log(f"Added simulation source: {dest}")
            self.load_file(dest)

    def load_file(self, path):
        for i, data in self.current_files.items():
            if data["path"] == path:
                self.tabs.setCurrentIndex(i)
                return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            title = os.path.basename(path)
            index = self.create_editor(content, title)
            ftype = "sim" if "simulations" in path else "design"
            self.current_files[index] = {"path": path, "type": ftype}
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open file: {e}")

    def save_file(self):
        index = self.tabs.currentIndex()
        if index < 0: return False

        file_data = self.current_files.get(index)
        if file_data and file_data["path"]:
            self.save_to_path(index, file_data["path"])
            return True
        else:
            default_dir = os.path.join(self.project_dir, "sources")
            if file_data and file_data["type"] == "sim":
                default_dir = os.path.join(self.project_dir, "simulations")
                
            path, _ = QFileDialog.getSaveFileName(self, "Save Source File", default_dir, "Verilog Files (*.v *.sv);;All Files (*.*)")
            if path:
                self.save_to_path(index, path)
                return True
        return False

    def save_to_path(self, index, path):
        try:
            editor = self.tabs.widget(index)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(editor.toPlainText())
            
            ftype = "sim" if "simulations" in path else "design"
            self.current_files[index] = {"path": path, "type": ftype}
            self.tabs.setTabText(index, os.path.basename(path))
            self.log(f"Saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save file: {e}")

    def log(self, message):
        self.console.appendPlainText(message)
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self):
        self.console.clear()

    def get_current_file_path(self):
        index = self.tabs.currentIndex()
        if index < 0: return None
        return self.current_files.get(index, {}).get("path")

    def simulate(self):
        for i in range(self.tabs.count()):
            self.tabs.setCurrentIndex(i)
            if not self.save_file():
                return
                
        self.clear_log()
        self.log("--- Starting Simulation Flow ---")
        
        sim_dir = os.path.join(self.project_dir, "simulations")
        src_dir = os.path.join(self.project_dir, "sources")
        out_vvp = os.path.join(sim_dir, "sim.vvp")
        
        design_files = glob.glob(os.path.join(src_dir, "*.v")) + glob.glob(os.path.join(src_dir, "*.sv"))
        tb_file = self.get_current_file_path()
        if not tb_file or not tb_file.startswith(sim_dir):
            sim_files = glob.glob(os.path.join(sim_dir, "*.v"))
            if sim_files:
                tb_file = sim_files[0]
            else:
                self.log("Error: Please open a Simulation Source file to run simulation.")
                return
                
        self.log(f"Using Testbench: {os.path.basename(tb_file)}")
        all_files = design_files + [tb_file]
        files_str = " ".join([f'"{f}"' for f in all_files])
        
        cmd = f'iverilog -o "sim.vvp" {files_str} && vvp "sim.vvp"'
        self.run_background_task(cmd, sim_dir)

    def synthesize(self):
        if not self.save_file(): return
        path = self.get_current_file_path()
        if not path:
            self.log("Error: Please open a Design Source to synthesize.")
            return

        self.clear_log()
        synth_dir = os.path.join(self.project_dir, "synthesis")
        filename = os.path.basename(path)
        
        self.log(f"--- Starting Synthesis Flow for {filename} ---")
        
        script = f"read_verilog {path}; hierarchy -auto-top; proc; opt; write_json synth_diagram.json"
        cmd = f'yosys -p "{script}" && netlistsvg synth_diagram.json -o synth_diagram.svg'
        
        self.run_background_task(cmd, synth_dir, on_success=lambda: self.post_synthesize(synth_dir))

    def post_synthesize(self, synth_dir):
        svg_path = os.path.join(synth_dir, "synth_diagram.svg")
        if os.path.exists(svg_path):
            self.log(f"Synthesis diagram saved: {svg_path}")
            self.log("Opening diagram in browser...")
            webbrowser.open(svg_path)
        else:
            self.log("Error: SVG file was not generated.")

    def view_waveform(self):
        sim_dir = os.path.join(self.project_dir, "simulations")
        vcd_files = [f for f in os.listdir(sim_dir) if f.endswith('.vcd')]
        
        if not vcd_files:
            QMessageBox.information(self, "No Waveforms", "No .vcd files found in the simulations folder.\nMake sure your testbench has $dumpfile and you've run Simulation.")
            return
            
        vcd_files.sort(key=lambda f: os.path.getmtime(os.path.join(sim_dir, f)), reverse=True)
        target = os.path.join(sim_dir, vcd_files[0])
        
        self.log(f"--- Opening {vcd_files[0]} in GTKWave ---")
        
        env = os.environ.copy()
        oss_bin = r"C:\oss-cad-suite\bin"
        env["PATH"] = f"{oss_bin};" + env.get("PATH", "")
        subprocess.Popen(f'gtkwave "{target}"', cwd=sim_dir, shell=True, env=env)

    def run_background_task(self, cmd, cwd, on_success=None):
        self.worker = WorkerThread(cmd, cwd)
        self.worker.output_signal.connect(self.log)
        
        def finished(code):
            self.log(f"\n--- Process finished with exit code {code} ---")
            if code == 0 and on_success:
                on_success()
                
        self.worker.finished_signal.connect(finished)
        self.worker.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    dialog = StartupDialog()
    if dialog.exec_() == QDialog.Accepted and dialog.project_dir:
        window = MainWindow(dialog.project_dir)
        window.show()
        sys.exit(app.exec_())
    else:
        sys.exit(0)
