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
                             QDialog, QPushButton, QLabel, QHBoxLayout, QStyle, QCompleter, QLineEdit, QAbstractItemView)
from PyQt5.QtCore import Qt, QProcess, QThread, pyqtSignal, QSize, QTimer, QStringListModel
from PyQt5.QtGui import QIcon, QFont, QImage, QPainter, QColor, QPixmap, QTextCursor
from PyQt5.QtSvg import QSvgRenderer

from code_editor import CodeEditor
from highlighter import VerilogHighlighter
import formatter

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
        self.setFixedSize(480, 220)
        self.setStyleSheet("QDialog { background-color: #21252B; } QLabel { color: #ABB2BF; } QPushButton { background-color: #3E4451; color: #ABB2BF; border: none; border-radius: 6px; padding: 10px; font-weight: bold; font-size: 11pt; } QPushButton:hover { background-color: #4B5263; }")
        self.project_dir = None
        
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        label = QLabel("Welcome to Verilog Studio\nCreate or open a project to continue.")
        label.setAlignment(Qt.AlignCenter)
        label.setFont(QFont("Segoe UI", 13))
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
        self.tabs.tabBar().installEventFilter(self)
        self.setCentralWidget(self.tabs)

        self.current_files = {} 
        
        self.init_ui()


    def eventFilter(self, source, event):
        if source == self.tabs.tabBar() and event.type() == event.MouseButtonRelease:
            if event.button() == Qt.MiddleButton:
                index = self.tabs.tabBar().tabAt(event.pos())
                if index >= 0:
                    self.close_tab(index)
                    return True
        return super().eventFilter(source, event)

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

        self.format_act = QAction("Format Code (Beautify)", self)
        self.format_act.setShortcut("Shift+Alt+F")
        self.format_act.triggered.connect(self.format_active_code)

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

        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction(self.format_act)

        self.view_menu = menubar.addMenu("View")

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
        self.console_dock = QDockWidget("Bottom Panel", self)
        self.console_dock.setObjectName("BottomPanelDock")
        self.console_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.console_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setDocumentMode(True)
        
        console_widget = QWidget()
        console_layout = QVBoxLayout()
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)
        
        self.console = ClickableConsole()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 12))
        self.console.setStyleSheet("background-color: #282C34; color: #ABB2BF; border: none; padding: 4px;")
        self.console.error_clicked.connect(self.jump_to_error)
        
        self.tcl_input = QLineEdit()
        self.tcl_input.setFont(QFont("Consolas", 12))
        self.tcl_input.setPlaceholderText("Tcl Console > type a command (simulate, synth, format) or a shell command and press Enter...")
        self.tcl_input.setStyleSheet("background-color: #21252B; color: #ABB2BF; border: 1px solid #181A1F; border-radius: 4px; padding: 8px;")
        self.tcl_input.returnPressed.connect(self.process_tcl_command)
        
        console_layout.addWidget(self.console)
        console_layout.addWidget(self.tcl_input)
        console_widget.setLayout(console_layout)
        
        from PyQt5.QtWidgets import QTableWidget, QHeaderView
        self.problems_table = QTableWidget()
        self.problems_table.setColumnCount(3)
        self.problems_table.setHorizontalHeaderLabels(["File", "Line", "Message"])
        self.problems_table.horizontalHeader().setStretchLastSection(True)
        self.problems_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.problems_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.problems_table.setStyleSheet("background-color: #282C34; color: #ABB2BF; gridline-color: #181A1F;")
        self.problems_table.itemDoubleClicked.connect(self.problem_clicked)
        
        self.synth_table = QTableWidget()
        self.synth_table.setColumnCount(2)
        self.synth_table.setHorizontalHeaderLabels(["Resource", "Utilization"])
        self.synth_table.horizontalHeader().setStretchLastSection(True)
        self.synth_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.synth_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.synth_table.setStyleSheet("background-color: #282C34; color: #ABB2BF; gridline-color: #181A1F;")
        
        self.bottom_tabs.addTab(console_widget, "Tcl Console")
        self.bottom_tabs.addTab(self.problems_table, "Problems")
        self.bottom_tabs.addTab(self.synth_table, "Synthesis Report")
        
        self.console_dock.setWidget(self.bottom_tabs)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)

        self.explorer_dock = QDockWidget("Project Explorer", self)
        self.explorer_dock.setObjectName("ProjectExplorerDock")
        self.explorer_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

    def problem_clicked(self, item):
        row = item.row()
        file_path = self.problems_table.item(row, 0).data(Qt.UserRole)
        line_num = int(self.problems_table.item(row, 1).text())
        
        if file_path and os.path.exists(file_path):
            self.load_file(file_path)
            editor = self.tabs.currentWidget()
            if editor:
                cursor = editor.textCursor()
                cursor.movePosition(cursor.Start)
                cursor.movePosition(cursor.Down, cursor.MoveAnchor, line_num - 1)
                editor.setTextCursor(cursor)
                editor.setFocus()
        self.explorer_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(self.project_dir)
        self.file_model.setReadOnly(False)
        
        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        self.tree.setRootIndex(self.file_model.index(self.project_dir))
        self.tree.doubleClicked.connect(self.tree_double_clicked)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setSelectionMode(QTreeView.ExtendedSelection)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setEditTriggers(QAbstractItemView.EditKeyPressed)
        self.tree.setStyleSheet("QTreeView { background-color: #21252B; color: #ABB2BF; border: none; font-size: 11pt; }"
                                "QTreeView::item { padding: 4px; border-radius: 4px; }"
                                "QTreeView::item:selected { background-color: #3E4451; color: #FFFFFF; }")
        
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_tree_menu)
        
        self.explorer_dock.setWidget(self.tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.explorer_dock)

        self.view_menu.addAction(self.explorer_dock.toggleViewAction())
        self.view_menu.addAction(self.console_dock.toggleViewAction())

    def process_tcl_command(self):
        cmd = self.tcl_input.text().strip()
        if not cmd:
            return
        
        self.tcl_input.clear()
        self.log(f"\nTcl> {cmd}")
        
        parts = cmd.split()
        base = parts[0].lower()
        
        if base == "simulate":
            self.simulate()
        elif base in ("synthesize", "synth"):
            self.synthesize()
        elif base == "format":
            self.format_active_code()
        elif base == "clear":
            self.console.clear()
        elif base == "exit":
            self.close()
        elif base == "help":
            self.log("Built-in Tcl/Agent Commands:")
            self.log("  simulate    - Run simulation (iverilog + vvp)")
            self.log("  synth       - Run synthesis (yosys + netlistsvg)")
            self.log("  format      - Auto-format current Verilog file")
            self.log("  clear       - Clear the console")
            self.log("  cd <dir>    - Change current directory")
            self.log("  pwd         - Print current directory")
            self.log("  exit        - Close Verilog Studio")
            self.log("Any other command will be executed as a system shell command.")
        elif base == "cd":
            if len(parts) > 1:
                target_dir = " ".join(parts[1:])
                if hasattr(self, 'console_cwd'):
                    target_dir = os.path.join(self.console_cwd, target_dir)
                else:
                    target_dir = os.path.join(self.project_dir, target_dir)
                target_dir = os.path.abspath(target_dir)
                if os.path.isdir(target_dir):
                    self.console_cwd = target_dir
                    self.log(f"Changed directory to {self.console_cwd}")
                else:
                    self.log(f"Error: Directory '{target_dir}' does not exist.")
            else:
                self.console_cwd = self.project_dir
                self.log(f"Changed directory to {self.console_cwd}")
        elif base == "pwd":
            cwd = getattr(self, 'console_cwd', self.project_dir)
            self.log(cwd)
        else:
            # Default to console_cwd, otherwise use active file's directory, otherwise project_dir
            if hasattr(self, 'console_cwd'):
                exec_dir = self.console_cwd
            else:
                active_path = self.get_current_file_path()
                exec_dir = os.path.dirname(active_path) if active_path else self.project_dir
            self.run_background_task(cmd, exec_dir)

    def open_tree_menu(self, position):
        indexes = self.tree.selectedIndexes()
        if not indexes:
            return
            
        # Get unique selected paths
        selected_paths = list(set([self.file_model.filePath(idx) for idx in indexes]))
        
        from PyQt5.QtWidgets import QMenu
        menu = QMenu()
        
        if len(selected_paths) == 1:
            index = [i for i in indexes if i.column() == 0][0]
            path = selected_paths[0]
            is_dir = os.path.isdir(path)
            
            new_file_act = menu.addAction("New File") if is_dir else None
            new_folder_act = menu.addAction("New Folder") if is_dir else None
            rename_act = menu.addAction("Rename")
            delete_act = menu.addAction("Delete")
            menu.addSeparator()
            reveal_act = menu.addAction("Reveal in Explorer")
            copy_path_act = menu.addAction("Copy Full Path")
            
            action = menu.exec_(self.tree.viewport().mapToGlobal(position))
            
            if action and action == new_file_act:
                self.create_new_file_in_tree(path)
            elif action and action == new_folder_act:
                self.create_new_folder_in_tree(path)
            elif action == rename_act:
                self.tree.edit(index)
            elif action == delete_act:
                self.delete_files_in_tree(selected_paths)
            elif action == reveal_act:
                import subprocess
                subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
            elif action == copy_path_act:
                QApplication.clipboard().setText(os.path.normpath(path))
        else:
            delete_act = menu.addAction(f"Delete {len(selected_paths)} items")
            action = menu.exec_(self.tree.viewport().mapToGlobal(position))
            
            if action == delete_act:
                self.delete_files_in_tree(selected_paths)

    def create_new_folder_in_tree(self, dir_path):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and name:
            new_path = os.path.join(dir_path, name)
            try:
                os.makedirs(new_path, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create folder: {e}")

    def create_new_file_in_tree(self, dir_path):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New File", "Enter file name:")
        if ok and name:
            new_path = os.path.join(dir_path, name)
            try:
                open(new_path, 'w').close()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def delete_files_in_tree(self, paths):
        msg = f"Are you sure you want to delete {os.path.basename(paths[0])}?" if len(paths) == 1 else f"Are you sure you want to delete {len(paths)} items?"
        reply = QMessageBox.question(self, "Confirm Delete", msg, QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            for path in paths:
                try:
                    if os.path.isdir(path):
                        import shutil
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not delete {path}:\n{str(e)}")

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
        editor.highlighter = VerilogHighlighter(editor.document())
        
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
            oss_lib = r"C:\oss-cad-suite\lib"
            env["PATH"] = f"{oss_bin};{oss_lib};" + env.get("PATH", "")
            
            # Find the path of the current editor to exclude it from the global list
            index = self.tabs.indexOf(editor)
            current_path = self.current_files.get(index, {}).get("path")
            
            # Load all other design/sim files so modules resolve without includes
            other_files = []
            for d in [os.path.join(self.project_dir, "sources"), os.path.join(self.project_dir, "simulations")]:
                if os.path.exists(d):
                    for f in glob.glob(os.path.join(d, "*.v")) + glob.glob(os.path.join(d, "*.sv")):
                        # Normalize paths to properly compare and exclude the currently edited file
                        if not current_path or os.path.normpath(f) != os.path.normpath(current_path):
                            other_files.append(f)
                            
            other_files_str = " ".join([f'"{f}"' for f in other_files])
            
            # Run iverilog syntax check only (-tnull)
            process = subprocess.Popen(f'iverilog -tnull {other_files_str} "{temp_name}"', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True, env=env)
            out, _ = process.communicate()
            
            error_lines = []
            temp_basename = os.path.basename(temp_name)
            
            from PyQt5.QtWidgets import QTableWidgetItem
            self.problems_table.setRowCount(0)
            
            # iverilog error format: file.v:line: error/warning: message
            for line_out in out.splitlines():
                # Example: C:\path\file.v:10: syntax error
                match = re.search(r'^(.*?):(\d+):\s*(.*)$', line_out)
                if match:
                    file_path = match.group(1).strip()
                    line_num_str = match.group(2)
                    msg = match.group(3).strip()
                    
                    if file_path.endswith(temp_basename):
                        # It's the current file
                        display_name = os.path.basename(current_path) if current_path else "Unsaved File"
                        actual_path = current_path
                        line_num = int(line_num_str) - 1 # 0-indexed for editor
                        error_lines.append(line_num)
                    else:
                        display_name = os.path.basename(file_path)
                        actual_path = file_path
                    
                    row = self.problems_table.rowCount()
                    self.problems_table.insertRow(row)
                    
                    item_file = QTableWidgetItem(display_name)
                    item_file.setData(Qt.UserRole, actual_path)
                    
                    item_line = QTableWidgetItem(line_num_str)
                    item_msg = QTableWidgetItem(msg)
                    
                    self.problems_table.setItem(row, 0, item_file)
                    self.problems_table.setItem(row, 1, item_line)
                    self.problems_table.setItem(row, 2, item_msg)
            
            editor.setErrors(error_lines)
            os.remove(temp_name)
        except Exception as e:
            pass # Ignore lint errors if tools missing

    def close_tab(self, index):
        if index in self.current_files:
            del self.current_files[index]
        self.tabs.removeTab(index)

    def format_active_code(self):
        index = self.tabs.currentIndex()
        if index == -1:
            return
            
        editor = self.tabs.widget(index)
        code = editor.toPlainText()
        
        try:
            from formatter import format_verilog
            formatted_code = format_verilog(code)
            
            # Update editor while preserving scroll and cursor if possible
            cursor = editor.textCursor()
            v_scroll = editor.verticalScrollBar().value()
            
            editor.setPlainText(formatted_code)
            
            editor.setTextCursor(cursor)
            editor.verticalScrollBar().setValue(v_scroll)
            self.log("Formatted active file.")
        except Exception as e:
            self.log(f"Formatting failed: {e}")

    def new_design_source(self):
        index = self.create_editor(title="Untitled_Design.v")
        self.current_files[index] = {"path": None, "type": "design"}

    def new_sim_source(self):
        index = self.create_editor(title="Untitled_Sim.v")
        self.current_files[index] = {"path": None, "type": "sim"}
        
    def add_design_source(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Design Sources", "", "Verilog & Data Files (*.v *.sv *.hex *.mem *.txt);;All Files (*.*)")
        for path in paths:
            if path:
                dest = os.path.join(self.project_dir, "sources", os.path.basename(path))
                shutil.copy(path, dest)
                self.log(f"Added design source: {dest}")
                self.load_file(dest)
            
    def add_sim_source(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Simulation Sources", "", "Verilog & Data Files (*.v *.sv *.hex *.mem *.txt);;All Files (*.*)")
        for path in paths:
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
        
        # Find the top module name from the current file
        editor = self.tabs.widget(self.tabs.currentIndex())
        code = editor.toPlainText()
        import re
        match = re.search(r'\bmodule\s+([a-zA-Z_0-9]+)', code)
        if not match:
            self.log(f"Error: Could not find a 'module' declaration in {filename}.")
            return
        top_module = match.group(1)
        self.log(f"Detected top module: {top_module}")
        
        # Load all design sources so includes aren't strictly necessary
        src_dir = os.path.join(self.project_dir, "sources")
        design_files = glob.glob(os.path.join(src_dir, "*.v")) + glob.glob(os.path.join(src_dir, "*.sv"))
        read_cmds = " ".join([f'read_verilog -overwrite "{f.replace(os.sep, "/")}";' for f in design_files])
        
        # prep (without flatten) preserves memory blocks and sub-modules as clean hierarchical boxes
        script = f"{read_cmds} prep -top {top_module}; tribuf -logic; opt; stat; write_json synth_diagram.json"
        cmd = f'yosys -l synth.log -p "{script}" && netlistsvg synth_diagram.json -o synth_diagram.svg'
        
        self.run_background_task(cmd, synth_dir, on_success=lambda: self.post_synthesize(synth_dir))

    def parse_synth_stats(self, log_path):
        if not os.path.exists(log_path):
            return
        
        self.synth_table.setRowCount(0)
        from PyQt5.QtWidgets import QTableWidgetItem
        
        try:
            with open(log_path, 'r') as f:
                content = f.read()
                
            import re
            # Find the final stats block
            match = re.search(r'=== design hierarchy ===(.*)', content, re.DOTALL)
            if not match:
                match = re.search(r'Printing statistics\.(.*)', content, re.DOTALL)
                
            if match:
                stats_text = match.group(1)
                # Look for lines like "   Number of wires:   33" or "   $add    1"
                for line in stats_text.splitlines():
                    line = line.strip()
                    if not line: continue
                    if line.startswith('Number of') or line.startswith('$'):
                        parts = [p.strip() for p in line.split(':')]
                        if len(parts) == 2:
                            name, val = parts
                        else:
                            parts = line.rsplit(maxsplit=1)
                            if len(parts) == 2:
                                name, val = parts
                            else:
                                continue
                                
                        row = self.synth_table.rowCount()
                        self.synth_table.insertRow(row)
                        self.synth_table.setItem(row, 0, QTableWidgetItem(name))
                        self.synth_table.setItem(row, 1, QTableWidgetItem(val))
        except Exception:
            pass

    def post_synthesize(self, synth_dir):
        svg_path = os.path.join(synth_dir, "synth_diagram.svg")
        log_path = os.path.join(synth_dir, "synth.log")
        self.parse_synth_stats(log_path)
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
        oss_lib = r"C:\oss-cad-suite\lib"
        env["PATH"] = f"{oss_bin};{oss_lib};" + env.get("PATH", "")
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



from PyQt5.QtGui import QPalette

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Set modern UI font
    app.setFont(QFont("Segoe UI", 10))
    
    # Global Dark Palette (One Dark Inspired)
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(33, 37, 43))
    dark_palette.setColor(QPalette.WindowText, QColor(171, 178, 191))
    dark_palette.setColor(QPalette.Base, QColor(40, 44, 52))
    dark_palette.setColor(QPalette.AlternateBase, QColor(33, 37, 43))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(171, 178, 191))
    dark_palette.setColor(QPalette.ToolTipText, QColor(171, 178, 191))
    dark_palette.setColor(QPalette.Text, QColor(171, 178, 191))
    dark_palette.setColor(QPalette.Button, QColor(33, 37, 43))
    dark_palette.setColor(QPalette.ButtonText, QColor(171, 178, 191))
    dark_palette.setColor(QPalette.BrightText, QColor(224, 108, 117))
    dark_palette.setColor(QPalette.Link, QColor(97, 175, 239))
    dark_palette.setColor(QPalette.Highlight, QColor(62, 68, 81))
    dark_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(dark_palette)
    
    app.setStyleSheet("""
        QMainWindow {
            background-color: #21252B;
        }
        QTabWidget::pane { 
            border: none;
            background-color: #282C34;
        }
        QTabBar::tab {
            background: #21252B;
            color: #7F848E;
            padding: 8px 16px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            border: none;
            margin-right: 2px;
            font-size: 10pt;
        }
        QTabBar::tab:selected {
            background: #282C34;
            color: #ABB2BF;
            border-top: 3px solid #61AFEF;
            font-weight: bold;
        }
        QTabBar::tab:hover:!selected {
            background: #2C313A;
            color: #ABB2BF;
        }
        QDockWidget {
            color: #ABB2BF;
            font-size: 11pt;
            titlebar-close-icon: url(close.png);
            titlebar-normal-icon: url(normal.png);
        }
        QDockWidget::title {
            background: #21252B;
            padding: 8px 12px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            font-weight: bold;
        }
        QMenuBar {
            background-color: #21252B;
            color: #ABB2BF;
            font-size: 10pt;
            padding: 4px;
        }
        QMenuBar::item {
            padding: 6px 12px;
            border-radius: 4px;
            margin-right: 4px;
        }
        QMenuBar::item:selected {
            background-color: #2C313A;
        }
        QMenu {
            background-color: #282C34;
            color: #ABB2BF;
            border: 1px solid #181A1F;
            border-radius: 6px;
            padding: 4px;
            font-size: 10pt;
        }
        QMenu::item {
            padding: 6px 24px 6px 24px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: #3E4451;
            color: #FFFFFF;
        }
        QToolBar {
            background-color: #21252B;
            border: none;
            padding: 6px;
            spacing: 8px;
        }
        QToolButton {
            border: none;
            border-radius: 4px;
            padding: 4px;
        }
        QToolButton:hover {
            background-color: #2C313A;
        }
        QToolButton:pressed {
            background-color: #3E4451;
        }
        QMessageBox {
            background-color: #282C34;
            color: #ABB2BF;
            font-size: 10pt;
        }
        QMessageBox QPushButton {
            background-color: #3E4451;
            color: #ABB2BF;
            border: none;
            border-radius: 4px;
            padding: 6px 16px;
            font-weight: bold;
        }
        QMessageBox QPushButton:hover {
            background-color: #4B5263;
            color: #FFFFFF;
        }
    """)
    
    # Fix path for PyInstaller
    import sys
    import os
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    
    app_icon = QIcon(os.path.join(base_path, "icon.png"))
    app.setWindowIcon(app_icon)
    
    dialog = StartupDialog()
    if dialog.exec_() == QDialog.Accepted and dialog.project_dir:
        window = MainWindow(dialog.project_dir)
        window.show()
        sys.exit(app.exec_())
    else:
        sys.exit(0)
