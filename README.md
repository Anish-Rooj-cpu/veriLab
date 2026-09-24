# Verilog Studio

A lightweight, fully-featured Verilog IDE for Windows that integrates code editing, simulation, waveform analysis, and schematic synthesis into a single, cohesive workflow. Built with Python and PyQt5, it seamlessly wraps popular open-source EDA tools.

## Key Features

* **Vivado-Style Project Management:** Create and open structured projects. The IDE automatically manages `sources/`, `simulations/`, and `synthesis/` directories to keep your workspace clean.
* **Project File Management:** Full support for standard Windows file operations in the Project Explorer. Right-click to rename or create files. Use `Ctrl+Click` or `Shift+Click` for multiple file selection, and bulk delete selected files.
* **Modern Code Editor:** A clean, tabbed interface featuring a VS Code-inspired Dark theme and intelligent Verilog/SystemVerilog syntax highlighting. 
  * **Rainbow Bracketing:** Verilog blocks (`module/endmodule`, `begin/end`, `case/endcase`) change colors based on their nesting depth to help visualize code structure.
  * **Monaco-Style Shortcuts:** 
    * `Alt + Click`: Drop multiple cursors to type in multiple places simultaneously.
    * `Alt + Up/Down`: Move the current line of code up or down.
    * `Shift + Alt + Up/Down`: Duplicate the current line of code.
* **Real-Time Linting & Clickable Console:** Syntax errors are checked in real-time as you type, underlining mistakes with red squiggles. The integrated console parses toolchain outputs; clicking on an error message instantly opens the file and jumps to the exact line number.
* **Intelligent Toolchain Loading:** The IDE automatically scans and loads all `.v` and `.sv` files in your project directory during compilation and synthesis. You no longer need to write ``` `include ``` statements at the top of your files to link modules.
* **One-Click Simulation:** Powered by Icarus Verilog (`iverilog` and `vvp`). Write your testbenches and click "Simulate" to instantly generate waveforms.
* **One-Click Synthesis:** Powered by Yosys and `netlistsvg`. Generates clean, industry-standard schematics directly in your web browser. The synthesis script automatically flattens your design hierarchy, rendering all internal logic and sub-modules onto a single comprehensive SVG diagram.
* **Integrated Tcl / Shell Console:** A built-in terminal dock at the bottom of the screen. Type built-in commands (`simulate`, `synth`, `format`, `clear`) or use it to execute standard system background shell commands (e.g., `git status`, `python script.py`) right in your project folder.
* **Waveform Viewer:** Launch GTKWave directly from the IDE to analyze your generated `.vcd` files instantly.

## Required External Tools

Verilog Studio acts as a front-end wrapper. To compile, simulate, and draw designs, the end-user must have the following open-source toolchains installed:

1. **OSS CAD Suite** (Provides `iverilog`, `yosys`, and `gtkwave`)
2. **Node.js / npm** (Provides the package manager required for diagram rendering)
3. **Graphviz** (Used by the rendering engine for routing wires on the schematic)

## Detailed Setup & Path Configuration

If you are distributing the compiled `Verilog Studio.exe`, the end-users do not need Python installed. However, they *must* have the toolchains installed at specific paths on their Windows system, or you will need to modify the hardcoded paths in `main.py` before building.

### 1. OSS CAD Suite Setup
1. Download the [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build/releases) for Windows.
2. Extract the archive directly to your `C:\` drive so that the resulting path is exactly `C:\oss-cad-suite`.
3. *(If you wish to use a different directory, you must modify `oss_bin` and `oss_lib` inside `main.py` to point to the new location.)*

### 2. Node.js & netlistsvg Setup
1. Download and install [Node.js](https://nodejs.org/).
2. Open a command prompt and install the netlistsvg engine globally by running:
   ```cmd
   npm install -g netlistsvg
   ```
3. The IDE expects this to be installed in the standard Windows APPDATA roaming folder for npm. 

### 3. Graphviz Setup
1. Download and install [Graphviz](https://graphviz.org/download/) for Windows.
2. During the installation, install it to the default path: `C:\Program Files\Graphviz`.
3. *(If installed elsewhere, modify `graphviz_bin` inside the `WorkerThread` class in `main.py`.)*

### Modifying Paths in the Source Code
If you need to change where Verilog Studio looks for these toolchains, open `main.py` and update the environment variable blocks located in:
* `WorkerThread.run()` (Handles Simulation and Synthesis processes)
* `lint_code()` (Handles background real-time syntax checking)
* `view_waveform()` (Handles opening GTKWave)

## Development & Building

The IDE itself is written purely in Python and PyQt5.

**Dependencies:**
```cmd
pip install PyQt5 PyInstaller
```

**Running from Source:**
```cmd
python main.py
```

**Building the Executable:**
We bundle the application using PyInstaller. Run the provided `build.bat` script, or run the following command in your terminal:
```cmd
python -m PyInstaller -y --name "Verilog Studio" --windowed --noconsole --icon=icon.ico --add-data "icon.png;." main.py
```
*(The compiled standalone executable will be generated inside the `dist/Verilog Studio/` folder.)*

## Usage Guide

1. **Launch:** Open `Verilog Studio.exe`.
2. **Start a Project:** Click "Create New Project" and select an empty folder on your PC.
3. **Write Code:** Click the blue `D*` icon to create a new Design Source, or the green `S*` icon to create a Simulation Source (Testbench).
4. **Format:** Hit `Ctrl+Shift+F` to automatically beautify and indent your Verilog code.
5. **Simulate:** Hit `F5` or click the Play button to compile and run your testbench.
6. **View Waves:** Hit `F7` or click the Screen button to open the latest waveform in GTKWave.
7. **Synthesize:** Hit `F6` or click the Link button to synthesize the active file and view the logic gate schematic.

## License
Open Source. Feel free to fork, modify, and improve!
