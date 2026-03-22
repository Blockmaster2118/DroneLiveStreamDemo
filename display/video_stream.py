import subprocess

rtsp_url = "rtsp://localhost:8554/dock1_stream"

subprocess.run([
    "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    rtsp_url,
    "--network-caching=100",   
])