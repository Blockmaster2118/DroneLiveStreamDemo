# Drone Sim — Setup Guide

This simulator runs on a Mac and streams telemetry, flight control, and live video to the AVP vROC app on an Apple Vision Pro over a local Wi-Fi network.

> **Note:** The simulator is functional and serves its purpose for development and testing, but it is not a polished production tool. Stream latency can vary, the physics are simplified, and some edge cases in manual flight mode may behave unexpectedly. It does the job.

> **Windows:** The simulator will not run on Windows as-is. The launcher (`launch_sim`) is a Bash script, and Mosquitto and MediaMTX are launched from Mac-specific Homebrew paths. It could theoretically be ported using WSL (Windows Subsystem for Linux) but this has not been tested and would require significant rework. Stick to a Mac.

---

## What you need before starting

A Mac running macOS. Apple Silicon (M1/M2/M3/M4) and Intel Macs both work, but there is one path difference for Apple Silicon noted in Steps 3 and 6.

---

## Step 1 — Install Homebrew

Homebrew is a package manager for Mac. Open **Terminal** (press Cmd+Space, type Terminal, press Enter) and paste this line, then press Enter:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow any prompts. If it asks for your password, type it (you won't see characters appear — that's normal) and press Enter.

---

## Step 2 — Install the required tools

In Terminal, run each of these one at a time, waiting for each to finish:

```bash
brew install mosquitto
brew install mediamtx
brew install ffmpeg
brew install node
pip3 install paho-mqtt
```

If `pip3 install` fails with an error about "externally managed environment", run this instead:

```bash
pip3 install paho-mqtt --break-system-packages
```

---

## Step 3 — Create the Mosquitto config file

Mosquitto needs a config file to allow connections from the Vision Pro on your local network. After installing it in Step 2, this file may not exist yet. Create it by running these two commands in Terminal:

```bash
mkdir -p /usr/local/etc/mosquitto
```

```bash
cat > /usr/local/etc/mosquitto/mosquitto.conf << 'EOF'
listener 1883
allow_anonymous true
EOF
```

This creates a minimal config that opens port 1883 and allows the Vision Pro to connect without a password.

**Apple Silicon Macs** — the path is different. Run these instead:

```bash
mkdir -p /opt/homebrew/etc/mosquitto
```

```bash
cat > /opt/homebrew/etc/mosquitto/mosquitto.conf << 'EOF'
listener 1883
allow_anonymous true
EOF
```

---

## Step 4 — Install the Node dependencies

In Terminal, navigate to the `api` folder inside the repo and run:

```bash
cd /path/to/DroneLiveStreamDemo/api
npm install
```

Replace `/path/to/DroneLiveStreamDemo` with wherever you cloned the repo on your Mac. For example: `/Users/yourname/Documents/DroneLiveStreamDemo`.

---

## Step 5 — Find your Mac's local IP address

The Vision Pro connects to the sim using your Mac's local network IP. To find it:

1. Open **System Settings**
2. Click **Wi-Fi**
3. Click **Details** next to your connected network
4. Your IP address is listed — it looks something like `192.168.0.34` or `10.72.54.74`

Or run this in Terminal:

```bash
ipconfig getifaddr en0
```

Write this IP down — you need it in the next two steps.

> **Important:** This IP can change every time you reconnect to Wi-Fi. If the app stops connecting on a future session, come back to this step and check whether the IP has changed, then redo Steps 6 and 7 with the new one.

---

## Step 6 — Edit the launcher file

`launch_sim` is in the root of the repo. It has two lines near the top that need to match your machine. To edit it:

1. Open **Xcode** (install it free from the Mac App Store if you don't have it)
2. In the menu bar go to **File → Open**
3. Navigate to the repo folder and open `launch_sim`
4. Find these two lines near the top:

```bash
REPO="/Users/adw/Documents/GitHub/DroneLiveStreamDemo"
MAC_IP="YOUR IP GOES HERE"
```

Change `REPO` to the full path of the repo folder on your Mac:
```bash
REPO="/Users/yourname/Documents/DroneLiveStreamDemo"
```

Change `MAC_IP` to the IP address you found in Step 5:
```bash
MAC_IP="192.168.0.34"
```

Save the file (Cmd+S).

**Apple Silicon Macs only** — also find this line:

```bash
/usr/local/opt/mosquitto/sbin/mosquitto -c /usr/local/etc/mosquitto/mosquitto.conf
```

And change it to:

```bash
/opt/homebrew/opt/mosquitto/sbin/mosquitto -c /opt/homebrew/etc/mosquitto/mosquitto.conf
```

Save again.

---

## Step 7 — Update the IP in the Vision Pro app

Open the Xcode project for the AVP vROC app, find `BridgeConfig.swift`, and change this line to your Mac's IP from Step 5:

```swift
static let host = "192.168.0.34"
```

Then rebuild and redeploy the app to the Vision Pro.

---

## Step 8 — Copy the launcher to /usr/local/bin so you can run it from anywhere

Right now `launch_sim` only runs if you are inside the repo folder in Terminal. This step copies it into `/usr/local/bin/` — a hidden system folder your Mac searches when you type any command — so you can type `launch_sim` from any Terminal window.

`/usr/local/bin/` is hidden and won't appear when browsing in Finder normally. If you ever need to get to it in a Finder window, press **Shift+Cmd+G**, type `/usr/local/bin` and press Enter to jump straight there.

To copy the file, run these two commands in Terminal. Replace the path in the first line with the actual location of your repo:

```bash
sudo cp /path/to/DroneLiveStreamDemo/launch_sim /usr/local/bin/launch_sim
sudo chmod +x /usr/local/bin/launch_sim
```

For example, if your repo is in Documents:

```bash
sudo cp /Users/yourname/Documents/DroneLiveStreamDemo/launch_sim /usr/local/bin/launch_sim
sudo chmod +x /usr/local/bin/launch_sim
```

`sudo` runs the command with admin privileges and will ask for your Mac password. Type it and press Enter (you won't see characters appear, that's normal).

The first line copies the file. The second marks it as executable so Terminal can run it as a command.

To confirm it worked, run:

```bash
which launch_sim
```

It should print `/usr/local/bin/launch_sim`.

---

## Running the simulator

Make sure your Mac and the Vision Pro are on the same Wi-Fi network, then open Terminal and type:

```bash
launch_sim
```

You will see coloured output from each service starting up. When you see `All services running`, open the app on the Vision Pro and it should connect.

To stop everything press **Ctrl+C** in the Terminal window.

If the simulator doesn't fully stop, run this to force-kill it:

```bash
pkill -f dock_sim.py
```

---

## Troubleshooting

**Vision Pro won't connect** — your Mac's IP has likely changed since you last set it up. Redo Steps 5, 6, and 7 with the new IP.

**`launch_sim` command not found** — Step 8 wasn't completed, or the path used was wrong. Try again with the correct path.

**Mosquitto won't start** — the config file is missing or in the wrong place. Redo Step 3. If you're on Apple Silicon, make sure you used the `/opt/homebrew/` paths.

**Stream doesn't appear in the app** — give it 10–15 seconds after launch as the stream takes a moment to start. If it still doesn't appear, check the Terminal output for any red errors from `[dock_sim]`.
