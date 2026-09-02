# Nova Tools

Welcome to the **Nova Tools** suite! This repository houses a collection of lightweight, standalone, and modular OSC (Open Sound Control) utilities and social loggers.

These tools are built in Python and can be run individually from source, or managed collectively using [Project-Proto](https://github.com/CaptainBoots/Project-Proto).

---

# Tools 

Each tool is located in its own subdirectory with its own logic and configurations:

## Tools Made By Boots

1. **OSC-Chatbox:** Sends custom text, system stats (CPU, GPU, RAM), time, and media playbacks to your VRChat chatbox using OSC. Integrates with Libre Hardware Monitor.
2. **OSC-FaceTrackingController:** Translates hardware facial tracking streams into standard OSC parameters for VRChat avatars.
3. **OSC-Gamepad:** Map controller buttons, joysticks, and triggers to specific VRChat avatar OSC parameters.
4. **OSC-ParameterBrowser:** An interactive UI for browsing, tracking, and debugging live OSC input/output parameters in real-time.
5. **OSC-Router:** Routes, filters, and splits incoming and outgoing OSC packets across multiple ports, allowing multiple OSC apps to run simultaneously.
6. **OSC-ScriptMaker:** Create, manage, and execute complex sequences of OSC events, movements, and avatar states.
7. **VRChat-Launcher:** Easily launch VRChat with custom arguments, launch options, and optimized performance environments.
8. **VRChat-LocalFavorites:** Manage, search, and group your favorite worlds and avatars locally, bypassing standard in-game limit restrictions.
9. **VRChat-SocialLogger:** Keep a private, locally logged record of joining, leaving, and social status events for friends.



## Verified Community Tools

Tool Name : Tool Description : Tool Maker

1. **Test:** (This is a placholder community tools will arrive soon) - Boots


---

##  Manual Installation & Setup

If you prefer to run these tools standalone without the main ToolBox:

### Prerequisites
Make sure you have Python 3.8+ installed.

### Install Dependencies
Each tool may have unique libraries. To install dependencies for a specific tool, navigate to its folder and install from its `dependency.txt` file (or install requirements):

```bash
# Example for installing OSC-Chatbox dependencies
cd OSC-Chatbox
pip install -r dependency.txt
```
Doing this is usually not needed as they will make there own virtual environments and install the dependency needed

### Running a Tool
Execute the tool's `main.py` entry point:
```bash
python main.py
```

---

##  Contribution & Feedback

If you have feature requests, bug fixes, or suggestions, feel free to open an issue or pull request! Join our community on Discord to discuss development:

### [**The Discord Server**](https://discord.gg/YDXpQPF6g9)

*Made with <3 by:*
1. Boots @CaptainBoots