import os
import sys
import platform
import subprocess

import numpy as np
import cv2
from rich import print as rprint

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.all_whisper_methods.demucs_vl import BACKGROUND_AUDIO_FILE
from core.step7_merge_sub_to_vid import check_gpu_available
from core.config_utils import load_key
from core.step1_ytdlp import find_video_files

DUB_VIDEO = "output/output_dub.mp4"
DUB_SUB_FILE = 'output/dub.srt'
DUB_AUDIO = 'output/dub.mp3'

def get_video_dimensions(video_file):
    """Get video dimensions using OpenCV"""
    cap = cv2.VideoCapture(video_file)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return width, height

def calculate_subtitle_style(width, height):
    """Calculate subtitle style based on video dimensions"""
    is_vertical = height > width
    aspect_ratio = min(width, height) / max(width, height)
    
    # Base font size on video dimensions
    base_font_size = min(width, height) / 36  # Adjust this divisor to change base font size
    
    # Adjust font size based on aspect ratio
    font_size = int(base_font_size * (1 + (1 - aspect_ratio)))
    
    # Adjust margins based on orientation
    if is_vertical:
        margin_v = int(height / 20)  # Smaller bottom margin for vertical videos
        max_line_length = int(width / (font_size * 0.6))  # Shorter lines for vertical videos
    else:
        margin_v = int(height / 10)  # Larger bottom margin for horizontal videos
        max_line_length = int(width / (font_size * 0.5))  # Longer lines for horizontal videos
    
    # Font settings
    font_name = 'NotoSansCJK-Regular' if platform.system() == 'Linux' else 'Arial'
    
    return {
        'font_size': font_size,
        'font_name': font_name,
        'margin_v': margin_v,
        'max_line_length': max_line_length,
        'font_color': '&H00FFFF',
        'outline_color': '&H000000',
        'outline_width': 1,
        'back_color': '&H33000000'
    }

def merge_video_audio():
    """Merge video and audio, and reduce video volume"""
    VIDEO_FILE = find_video_files()
    background_file = BACKGROUND_AUDIO_FILE
    
    if load_key("resolution") == '0x0':
        rprint("[bold yellow]Warning: A 0-second black video will be generated as a placeholder as Resolution is set to 0x0.[/bold yellow]")

        # Create a black frame
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(DUB_VIDEO, fourcc, 1, (1920, 1080))
        out.write(frame)
        out.release()

        rprint("[bold green]Placeholder video has been generated.[/bold green]")
        return

    # Get video dimensions and calculate subtitle style
    video_width, video_height = get_video_dimensions(VIDEO_FILE)
    subtitle_style = calculate_subtitle_style(video_width, video_height)
    
    # Merge video and audio with translated subtitles
    dub_volume = load_key("dub_volume")
    resolution = load_key("resolution")
    
    # Use original dimensions if resolution is set to 'original'
    if resolution == 'original':
        target_width, target_height = video_width, video_height
    else:
        target_width, target_height = resolution.split('x')
    
    subtitle_filter = (
        f"subtitles={DUB_SUB_FILE}:force_style='FontSize={subtitle_style['font_size']},"
        f"FontName={subtitle_style['font_name']},PrimaryColour={subtitle_style['font_color']},"
        f"OutlineColour={subtitle_style['outline_color']},OutlineWidth={subtitle_style['outline_width']},"
        f"BackColour={subtitle_style['back_color']},Alignment=2,MarginV={subtitle_style['margin_v']},BorderStyle=4'"
    )
    
    cmd = [
        'ffmpeg', '-y', '-i', VIDEO_FILE, '-i', background_file, '-i', DUB_AUDIO,
        '-filter_complex',
        f'[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
        f'pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,'
        f'{subtitle_filter}[v];'
        f'[1:a]volume=1[a1];[2:a]volume={dub_volume}[a2];'
        f'[a1][a2]amix=inputs=2:duration=first:dropout_transition=3[a]'
    ]

    if check_gpu_available():
        rprint("[bold green]Using GPU acceleration...[/bold green]")
        cmd.extend(['-map', '[v]', '-map', '[a]', '-c:v', 'h264_nvenc'])
    else:
        cmd.extend(['-map', '[v]', '-map', '[a]'])
    
    cmd.extend(['-c:a', 'aac', '-b:a', '192k', DUB_VIDEO])
    
    subprocess.run(cmd)
    rprint(f"[bold green]Video and audio successfully merged into {DUB_VIDEO}[/bold green]")

if __name__ == '__main__':
    merge_video_audio()
