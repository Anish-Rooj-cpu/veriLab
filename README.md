# Verilog Studio 🚀

A lightweight, fully-featured Verilog IDE for Windows that integrates code editing, simulation, waveform analysis, and schematic synthesis into a single, cohesive, Vivado-style workflow. Built with Python and PyQt5, it seamlessly wraps popular open-source EDA tools.

## Features ✨

* **Vivado-Style Project Management:** Create and open structured projects. The IDE automatically manages `sources/`, `simulations/`, and `synthesis/` directories to keep your workspace clean.
* **Modern Code Editor:** A clean, tabbed interface with line numbers, intelligent Verilog/SystemVerilog syntax highlighting, and standard "document mode" styling.
* **One-Click Simulation (Icarus Verilog):** Write your testbenches and click "Simulate". Verilog Studio instantly compiles all your design sources, links your active testbench, and generates waveforms straight into your `simulations/` folder.
* **One-Click Synthesis (Yosys + netlistsvg):** Click "Synthesize" to run Yosys on your design. Instead of messy graph outputs, Verilog Studio uses `netlistsvg` to draw clean, industry-standard schematics (with D-Flip Flops, logic gates, and splitters). The generated SVG is automatically opened in your default web browser for native zooming, panning, and perfect CSS rendering.
* **Waveform Viewer (GTKWave):** Launch GTKWave directly from the IDE to analyze your generated `.vcd` files instantly.
* **Smart File Import:** Use the colorful toolbar to "Add Design Source" or "Add Simulation Source", which automatically copies files from anywhere on your disk directly into your structured project hierarchy.

## Prerequisites 🛠️

To use Verilog Studio, you must have the **OSS CAD Suite** installed on your system.
1. Download [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build/releases) for Windows.
2. Extract the folder to `C:\oss-cad-suite` (or update the path inside `main.py`).
3. Ensure you have Node.js/npm installed, and install `netlistsvg` globally:
   ```bash
   npm install -g netlistsvg
   ```
4. Install **Graphviz** for Windows, and ensure it is located at `C:\Program Files\Graphviz\bin` (used by netlistsvg layout).

## Development & Building 💻

The IDE is written in Python (PyQt5). 

**Dependencies:**
```bash
pip install PyQt5
```

**Running from Source:**
```bash
python main.py
```

**Building the Executable:**
We bundle the application using PyInstaller:
```bash
python -m PyInstaller -y --name "Verilog Studio" --windowed --noconsole main.py
```
*(The compiled executable will be located in `dist/Verilog Studio/Verilog Studio.exe`)*

## Usage Guide 📖

1. **Launch:** Open `Verilog Studio.exe`.
2. **Start a Project:** Click "Create New Project" and select an empty folder on your PC.
3. **Write Code:** Click the blue `D*` icon to create a new Design Source, or the green `S*` icon to create a Simulation Source (Testbench).
4. **Simulate:** Hit `F5` or click the Play button to compile and run your testbench.
5. **View Waves:** Hit `F7` or click the Screen button to open the latest waveform in GTKWave.
6. **Synthesize:** Hit `F6` or click the Link button to synthesize the active file. The high-res schematic SVG will automatically open in your web browser!

## License
Open Source. Feel free to fork, modify, and improve!
