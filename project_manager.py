import json
import os

def save_workspace(project_dir, tabs_paths, active_index, window_geometry=None, window_state=None):
    vprj_path = os.path.join(project_dir, "project.vprj")
    data = {
        "open_tabs": tabs_paths,
        "active_index": active_index,
        "window_geometry": window_geometry,
        "window_state": window_state
    }
    try:
        with open(vprj_path, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

def load_workspace(project_dir):
    vprj_path = os.path.join(project_dir, "project.vprj")
    if os.path.exists(vprj_path):
        try:
            with open(vprj_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None
