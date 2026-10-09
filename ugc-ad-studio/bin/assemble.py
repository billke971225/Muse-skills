#!/usr/bin/env python3
"""UGC ad assembler template: beats -> captioned 9:16 segments -> concat.
Copy to project dir and fill BEATS. Requires: ffmpeg, DejaVu fonts.

Each beat: trim source clip to narration length, scale/crop to 720x1280
(or 1080x1920 for final delivery), burn caption inside Meta safe zone
(bottom 35% clear), mux narration audio.
"""
import subprocess, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "beats")
os.makedirs(OUT, exist_ok=True)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# --- FILL ME ---------------------------------------------------------------
# (name, video_src, start_sec, caption_text with \n for line breaks)
BEATS = [
    # ("beat1", "src/hook.mp4", 2, "Hook line one\nHook line two"),
]
NARRATION_DIR = os.path.join(BASE, "narration")   # beatN.mp3 files
FINAL = os.path.join(BASE, "ugc-ad-final.mp4")
# 720x1280 for drafts; 1080x1920 for delivery
W, H = 720, 1280
# ---------------------------------------------------------------------------

def dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())

def main():
    if not BEATS:
        sys.exit("fill BEATS first")
    files = []
    for name, src, ss, caption in BEATS:
        apath = os.path.join(NARRATION_DIR, name + ".mp3")
        capfile = os.path.join(OUT, name + ".txt")
        open(capfile, "w").write(caption)
        d = dur(apath) + 0.4
        out = os.path.join(OUT, name + ".mp4")
        # caption sits above the 35% bottom safe zone
        safe_bottom = int(H * 0.38)
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"drawtext=fontfile={FONT}:textfile={capfile}:fontsize={int(W*0.044)}:"
              f"fontcolor=white:borderw=3:bordercolor=black:"
              f"x=(w-text_w)/2:y=h-text_h-{safe_bottom},"
              f"fps=30,format=yuv420p")
        cmd = ["ffmpeg", "-y", "-v", "error",
               "-ss", str(ss), "-i", src, "-i", apath,
               "-vf", vf, "-t", str(d),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
               "-c:a", "aac", "-b:a", "128k", "-shortest", out]
        print("building", name, flush=True)
        subprocess.run(cmd, check=True)
        files.append(out)
    lst = os.path.join(OUT, "list.txt")
    with open(lst, "w") as f:
        for p in files:
            f.write(f"file '{p}'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy", FINAL], check=True)
    print("FINAL:", FINAL, dur(FINAL))

if __name__ == "__main__":
    main()
