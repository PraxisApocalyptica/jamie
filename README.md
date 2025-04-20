# Jamie: The Robotic Companion

This repository contains the code and documentation for Jamie, a mobile robotic companion designed for interaction, perception, and manipulation in a home environment. Named after my pet, Jamie aims to be a friendly assistant.

The project utilizes a multi-device architecture:
- **Vision (Cross-Platform App):** Runs on a smartphone (Android/iOS). The app handles perception (camera feed, SLAM via ARCore/ARKit, AI vision like YOLO-Seg) and user interaction (voice input/output, potential UI).
- **Brain (Raspberry Pi/Jetson):** The central processing unit running high-level AI (Natural Language Understanding, Dialogue Management, Task Planning, LLM interface) and robotics algorithms (SLAM integration, Inverse Kinematics, Grasp Planning, Navigation). Integrates data from additional sensors (3D camera, encoders, force sensor).
- **Motion (Arduino Mega):** The low-level controller executing commands from the Brain to control motors (base movement), servos (pan-tilt, arm joints, gripper), and read basic sensors (bump sensors).

**Project Goal:**
The long-term aspiration is to create a robot capable of natural language interaction, understanding its environment, navigating autonomously, and manipulating objects in the real world to act as a helpful and engaging companion. The aim is to achieve a high level of reliability for these tasks within the house environment.

**Additional Guide:**
Progress and development of this project are documented on a YouTube channel: https://www.youtube.com/@doomsdayrobotics9170.

**Current Status:**
This is a highly ambitious, long-term hobby project and a work in progress. Code in this repository is a conceptual framework with placeholders and is not yet a fully functioning robot. Many components require significant implementation, calibration, and integration.

**Getting Started:**

1.  **Hardware:** Assemble the robot hardware (mobile base, body, arm, pan-tilt head, sensors, power). Refer to `docs/` for diagrams and notes.
2.  **Setup:**
    *   Set up the Arduino (Motion) with the code from the `motion/` directory.
    *   Set up the Raspberry Pi (Brain) with the code from the `brain/` directory and install dependencies.
    *   Set up the Android phone (Vision) by building the app from `vision/android/`. (Note: Requires setting up a cross-platform framework project if starting from scratch, and integrating this native Android code).
    *   (If targeting iOS) Set up an Apple device with the iOS app built from `vision/ios/` (Requires writing the iOS native code).
3.  **Configuration:** Update configuration files (e.g., `brain/config/robot_config.yaml`) with your specific hardware details, API keys, and calibration parameters.
4.  **Calibration:** Perform necessary hardware calibration steps (camera transforms, encoder tuning, arm kinematics). Refer to `docs/calibration.md`.
5.  **Run:** Start the components in the correct order (Arduino -> Raspberry Pi -> Android/iOS App).

**Code Structure:**

- `vision/`: Cross-platform project root (e.g., React Native, Flutter). Contains native code subdirectories (`android/`, `ios/`) and potentially shared code.
    - `vision/android/`: Android native project code (Java/Kotlin) specific to the Android platform's vision/speech/communication interfaces.
    - `vision/ios/`: iOS native project code (Swift/Objective-C) for Apple devices. (Needs implementation).
- `brain/`: Raspberry Pi / Jetson code (Central Brain) - The core AI, robotics, and integration logic.
- `motion/`: Arduino sketches and related code (Low-Level Motion control) - Direct hardware control.
- `docs/`: Project documentation, diagrams, and notes.
- `data/`: Datasets for testing or training.

**Contributing:**

This is primarily a personal hobby project documented for learning and content creation. While direct contributions are not actively sought for this personal project, feedback and suggestions on the concepts or specific implementations are welcome. Feel free to open issues for discussion.

**License:**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Contact:**

Doomsday - [Your Contact Information, e.g., email, social media handle]

https://www.youtube.com/@doomsdayrobotics9170
