import os, sys
import glob
import shutil
import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def cleanup(history_dir="history"):
    # 获取output目录下所有视频文件（原始和生成）
    video_files = [f for f in os.listdir('output') if f.split('.')[-1].lower() in ['mp4','mov','avi','mkv','flv','wmv','webm']]
    if len(video_files) == 0:
        raise FileNotFoundError('No video file found in the output directory.')
    os.makedirs(history_dir, exist_ok=True)
    processed_files = set()
    for video_file in video_files:
        video_name = os.path.splitext(video_file)[0]
        video_name = sanitize_filename(video_name)
        # 归档目录，若重名则加时间戳
        video_history_dir = os.path.join(history_dir, video_name)
        if os.path.exists(video_history_dir):
            video_history_dir += '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs(video_history_dir)
        # 创建子目录
        log_dir = os.path.join(video_history_dir, "log")
        gpt_log_dir = os.path.join(video_history_dir, "gpt_log")
        audio_dir = os.path.join(video_history_dir, "audio")
        os.makedirs(log_dir, exist_ok=True)
        os.makedirs(gpt_log_dir, exist_ok=True)
        os.makedirs(audio_dir, exist_ok=True)
        # 归档output下的文件
        for file in os.listdir('output'):
            src = os.path.join('output', file)
            if file in processed_files:
                continue
            if os.path.isfile(src):
                # 所有视频文件都移动
                if file.split('.')[-1].lower() in ['mp4','mov','avi','mkv','flv','wmv','webm']:
                    shutil.move(src, os.path.join(video_history_dir, file))
                    processed_files.add(file)
                elif file.endswith('.srt'):
                    shutil.move(src, os.path.join(video_history_dir, file))
                    processed_files.add(file)
            elif os.path.isdir(src):
                if file == 'audio':
                    shutil.move(src, audio_dir)
                    processed_files.add(file)
                elif file == 'log':
                    shutil.move(src, log_dir)
                    processed_files.add(file)
                elif file == 'gpt_log':
                    shutil.move(src, gpt_log_dir)
                    processed_files.add(file)
                else:
                    shutil.move(src, os.path.join(video_history_dir, file))
                    processed_files.add(file)
    # 最后彻底清空output目录
    for f in os.listdir('output'):
        fp = os.path.join('output', f)
        try:
            if os.path.isfile(fp):
                os.remove(fp)
            elif os.path.isdir(fp):
                shutil.rmtree(fp)
        except Exception as e:
            print(f"Failed to delete {fp}: {e}")

def move_file(src, dst):
    try:
        # Get the source file name
        src_filename = os.path.basename(src)
        # Use os.path.join to ensure correct path and include file name
        dst = os.path.join(dst, sanitize_filename(src_filename))
        
        if os.path.exists(dst):
            if os.path.isdir(dst):
                # If destination is a folder, try to delete its contents
                shutil.rmtree(dst, ignore_errors=True)
            else:
                # If destination is a file, try to delete it
                os.remove(dst)
        
        shutil.move(src, dst, copy_function=shutil.copy2)
        print(f"✅ Moved: {src} -> {dst}")
    except PermissionError:
        print(f"⚠️ Permission error: Cannot delete {dst}, attempting to overwrite")
        try:
            shutil.copy2(src, dst)
            os.remove(src)
            print(f"✅ Copied and deleted source file: {src} -> {dst}")
        except Exception as e:
            print(f"❌ Move failed: {src} -> {dst}")
            print(f"Error message: {str(e)}")
    except Exception as e:
        print(f"❌ Move failed: {src} -> {dst}")
        print(f"Error message: {str(e)}")

def sanitize_filename(filename):
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

if __name__ == "__main__":
    cleanup()