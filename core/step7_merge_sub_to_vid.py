import os, subprocess, time, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config_utils import load_key
from rich import print as rprint
import cv2
import numpy as np
import platform

SRC_FONT_SIZE = 15
TRANS_FONT_SIZE = 17
FONT_NAME = 'Arial'
TRANS_FONT_NAME = 'Arial'

# Linux need to install google noto fonts: apt-get install fonts-noto
if platform.system() == 'Linux':
    FONT_NAME = 'NotoSansCJK-Regular'
    TRANS_FONT_NAME = 'NotoSansCJK-Regular'

SRC_FONT_COLOR = '&HFFFFFF'
SRC_OUTLINE_COLOR = '&H000000'
SRC_OUTLINE_WIDTH = 1
SRC_SHADOW_COLOR = '&H80000000'
TRANS_FONT_COLOR = '&H00FFFF'
TRANS_OUTLINE_COLOR = '&H000000'
TRANS_OUTLINE_WIDTH = 1 
TRANS_BACK_COLOR = '&H33000000'

def get_output_dir(history_dir):
    return history_dir
def get_output_video(history_dir):
    return os.path.join(history_dir, "output_sub.mp4")
def get_src_srt(history_dir):
    return os.path.join(history_dir, "src.srt")
def get_trans_srt(history_dir):
    return os.path.join(history_dir, "trans.srt")

def check_gpu_available():
    try:
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
        return 'h264_nvenc' in result.stdout
    except:
        return False

def merge_subtitles_to_video(history_dir):
    RESOLUTION = load_key("resolution")
    output_dir = get_output_dir(history_dir)
    output_video = get_output_video(history_dir)
    src_srt = get_src_srt(history_dir)
    trans_srt = get_trans_srt(history_dir)
    video_files = [f for f in os.listdir(output_dir) if f.split('.')[-1].lower() in ['mp4','mov','avi','mkv','flv','wmv','webm']]
    if len(video_files) != 1:
        raise FileNotFoundError('Please upload exactly one video file to the output directory.')
    video_file = os.path.join(output_dir, video_files[0])
    if RESOLUTION.lower() == "original":
        cap = cv2.VideoCapture(video_file)
        if not cap.isOpened():
            rprint("Error: Unable to open video file.")
            exit(1)
        TARGET_WIDTH = str(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
        TARGET_HEIGHT = str(int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        cap.release()
    else:
        TARGET_WIDTH, TARGET_HEIGHT = RESOLUTION.split('x')

    os.makedirs(os.path.dirname(output_video), exist_ok=True)

    # Check resolution
    if RESOLUTION == '0x0':
        rprint("[bold yellow]Warning: A 0-second black video will be generated as a placeholder as Resolution is set to 0x0.[/bold yellow]")

        # Create a black frame
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(get_output_video(history_dir), fourcc, 1, (1920, 1080))
        out.write(frame)
        out.release()

        rprint("[bold green]Placeholder video has been generated.[/bold green]")
        return

    if not os.path.exists(get_src_srt(history_dir)) or not os.path.exists(get_trans_srt(history_dir)):
        print("Subtitle files not found in the 'output' directory.")
        exit(1)

    # 判断竖屏还是横屏，动态调整字幕MarginV（支持config.yaml自定义）
    import yaml
    def load_margin_v():
        default = {'src': {'vertical': 200, 'horizontal': 54}, 'trans': {'vertical': 100, 'horizontal': 27}}
        try:
            with open('config.yaml', 'r') as f:
                cfg = yaml.safe_load(f)
                return cfg.get('subtitle', {}).get('margin_v', default)
        except Exception:
            return default
    margin_v = load_margin_v()
    try:
        w, h = int(TARGET_WIDTH), int(TARGET_HEIGHT)
    except Exception:
        w, h = 1920, 1080
    is_vertical = h > w
    if is_vertical:
        src_margin = margin_v['src'].get('vertical', 200)
        trans_margin = margin_v['trans'].get('vertical', 100)
    else:
        src_margin = margin_v['src'].get('horizontal', 54)
        trans_margin = margin_v['trans'].get('horizontal', 27)

    ffmpeg_cmd = [
        'ffmpeg', '-i', video_file,
        '-vf', (
            f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
            f"subtitles={get_src_srt(history_dir)}:force_style='FontSize={SRC_FONT_SIZE},FontName={FONT_NAME},"
            f"PrimaryColour={SRC_FONT_COLOR},OutlineColour={SRC_OUTLINE_COLOR},OutlineWidth={SRC_OUTLINE_WIDTH},"
            f"ShadowColour={SRC_SHADOW_COLOR},BorderStyle=1,MarginV={src_margin}',"
            f"subtitles={get_trans_srt(history_dir)}:force_style='FontSize={TRANS_FONT_SIZE},FontName={TRANS_FONT_NAME},"
            f"PrimaryColour={TRANS_FONT_COLOR},OutlineColour={TRANS_OUTLINE_COLOR},OutlineWidth={TRANS_OUTLINE_WIDTH},"
            f"BackColour={TRANS_BACK_COLOR},Alignment=2,MarginV={trans_margin},BorderStyle=4'"
        ).encode('utf-8'),
    ]

    gpu_available = check_gpu_available()
    if gpu_available:
        rprint("[bold green]NVIDIA GPU encoder detected, will use GPU acceleration.[/bold green]")
        ffmpeg_cmd.extend(['-c:v', 'h264_nvenc'])
    else:
        rprint("[bold yellow]No NVIDIA GPU encoder detected, will use CPU instead.[/bold yellow]")
    
    ffmpeg_cmd.extend(['-y', get_output_video(history_dir)])

    print("🎬 Start merging subtitles to video...")
    start_time = time.time()
    process = subprocess.Popen(ffmpeg_cmd)

    try:
        process.wait()
        if process.returncode == 0:
            print(f"\n✅ Done! Time taken: {time.time() - start_time:.2f} seconds")
        else:
            print("\n❌ FFmpeg execution error")
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        if process.poll() is None:
            process.kill()

if __name__ == "__main__":
    merge_subtitles_to_video()