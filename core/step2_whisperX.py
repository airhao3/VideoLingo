import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import warnings
warnings.filterwarnings("ignore")

import whisperx
import torch
from typing import Dict
import librosa
from rich import print as rprint
import subprocess
import tempfile
import time

from core.config_utils import load_key
from core.all_whisper_methods.demucs_vl import demucs_main, get_raw_audio_file, get_vocal_audio_file, get_background_audio_file
from core.all_whisper_methods.whisperX_utils import process_transcription, convert_video_to_audio, split_audio, save_results, save_language, compress_audio, get_cleaned_chunks_excel_path

MODEL_DIR = load_key("model_dir")
def get_whisper_file(history_dir):
    return os.path.join(history_dir, "audio", "for_whisper.mp3")
def get_enhanced_vocal_path(history_dir):
    return os.path.join(history_dir, "audio", "enhanced_vocals.mp3")
def get_cleaned_chunks_excel_path(history_dir):
    return os.path.join(history_dir, "log", "cleaned_chunks.xlsx")

def check_hf_mirror() -> str:
    """Check and return the fastest HF mirror"""
    mirrors = {
        'Official': 'huggingface.co',
        'Mirror': 'hf-mirror.com'
    }
    fastest_url = f"https://{mirrors['Official']}"
    best_time = float('inf')
    rprint("[cyan]🔍 Checking HuggingFace mirrors...[/cyan]")
    for name, domain in mirrors.items():
        try:
            if os.name == 'nt':
                cmd = ['ping', '-n', '1', '-w', '3000', domain]
            else:
                cmd = ['ping', '-c', '1', '-W', '3', domain]
            start = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True)
            response_time = time.time() - start
            if result.returncode == 0:
                if response_time < best_time:
                    best_time = response_time
                    fastest_url = f"https://{domain}"
                rprint(f"[green]✓ {name}:[/green] {response_time:.2f}s")
        except:
            rprint(f"[red]✗ {name}:[/red] Failed to connect")
    if best_time == float('inf'):
        rprint("[yellow]⚠️ All mirrors failed, using default[/yellow]")
    rprint(f"[cyan]🚀 Selected mirror:[/cyan] {fastest_url} ({best_time:.2f}s)")
    return fastest_url

def transcribe_audio(audio_file: str, start: float, end: float) -> Dict:
    os.environ['HF_ENDPOINT'] = check_hf_mirror() #? don't know if it's working...
    WHISPER_LANGUAGE = load_key("whisper.language")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    rprint(f"🚀 Starting WhisperX using device: {device} ...")
    
    if device == "cuda":
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        batch_size = 16 if gpu_mem > 8 else 2
        compute_type = "float16" if torch.cuda.is_bf16_supported() else "int8"
        rprint(f"[cyan]🎮 GPU memory:[/cyan] {gpu_mem:.2f} GB, [cyan]📦 Batch size:[/cyan] {batch_size}, [cyan]⚙️ Compute type:[/cyan] {compute_type}")
    else:
        batch_size = 1
        compute_type = "int8"
        rprint(f"[cyan]📦 Batch size:[/cyan] {batch_size}, [cyan]⚙️ Compute type:[/cyan] {compute_type}")
    rprint(f"[green]▶️ Starting WhisperX for segment {start:.2f}s to {end:.2f}s...[/green]")
    
    try:
        if WHISPER_LANGUAGE == 'zh':
            model_name = "Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper"
            local_model = os.path.join(MODEL_DIR, "Belle-whisper-large-v3-zh-punct-fasterwhisper")
        else:
            model_name = load_key("whisper.model")
            local_model = os.path.join(MODEL_DIR, model_name)
            
        if os.path.exists(local_model):
            rprint(f"[green]📥 Loading local WHISPER model:[/green] {local_model} ...")
            model_name = local_model
        else:
            rprint(f"[green]📥 Using WHISPER model from HuggingFace:[/green] {model_name} ...")

        vad_options = {"vad_onset": 0.500,"vad_offset": 0.363}
        asr_options = {"temperatures": [0],"initial_prompt": "",}
        whisper_language = None if 'auto' in WHISPER_LANGUAGE else WHISPER_LANGUAGE
        rprint("[bold yellow]**You can ignore warning of `Model was trained with torch 1.10.0+cu102, yours is 2.0.0+cu118...`**[/bold yellow]")
        model = whisperx.load_model(model_name, device, compute_type=compute_type, language=whisper_language, vad_options=vad_options, asr_options=asr_options, download_root=MODEL_DIR)

        # Create temp file with wav format for better compatibility
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
            temp_audio_path = temp_audio.name
        
        # Extract audio segment using ffmpeg
        ffmpeg_cmd = f'ffmpeg -y -i "{audio_file}" -ss {start} -t {end-start} -vn -ar 32000 -ac 1 "{temp_audio_path}"'
        subprocess.run(ffmpeg_cmd, shell=True, check=True, capture_output=True)
        
        try:
            # Load audio segment with librosa
            audio_segment, sample_rate = librosa.load(temp_audio_path, sr=16000)
        finally:
            # Clean up temp file
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)

        rprint("[bold green]note: You will see Progress if working correctly[/bold green]")
        result = model.transcribe(audio_segment, batch_size=batch_size, print_progress=True)

        # Free GPU resources
        del model
        torch.cuda.empty_cache()

        # Save language
        save_language(result['language'])
        if result['language'] == 'zh' and WHISPER_LANGUAGE != 'zh':
            raise ValueError("Please specify the transcription language as zh and try again!")

        # Align whisper output
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
        result = whisperx.align(result["segments"], model_a, metadata, audio_segment, device, return_char_alignments=False)

        # Free GPU resources again
        torch.cuda.empty_cache()
        del model_a

        # Adjust timestamps
        for segment in result['segments']:
            segment['start'] += start
            segment['end'] += start
            for word in segment['words']:
                if 'start' in word:
                    word['start'] += start
                if 'end' in word:
                    word['end'] += start
        return result
    except Exception as e:
        rprint(f"[red]WhisperX processing error:[/red] {e}")
        raise

def enhance_vocals(history_dir, vocals_ratio=2.50):
    """Enhance vocals audio volume"""
    if not load_key("demucs"):
        return get_raw_audio_file(history_dir)
    try:
        print(f"[cyan]🎙️ Enhancing vocals with volume ratio: {vocals_ratio}[/cyan]")
        vocal_audio_file = get_vocal_audio_file(history_dir)
        enhanced_vocal_path = get_enhanced_vocal_path(history_dir)
        ffmpeg_cmd = (
            f'ffmpeg -y -i "{vocal_audio_file}" '
            f'-filter:a "volume={vocals_ratio}" '
            f'"{enhanced_vocal_path}"'
        )
        subprocess.run(ffmpeg_cmd, shell=True, check=True, capture_output=True)
        return enhanced_vocal_path
    except subprocess.CalledProcessError as e:
        print(f"[red]Error enhancing vocals: {str(e)}[/red]")
        return vocal_audio_file  # Fallback to original vocals if enhancement fails
    
def transcribe(history_dir):
    os.makedirs(os.path.join(history_dir, "audio"), exist_ok=True)
    os.makedirs(os.path.join(history_dir, "log"), exist_ok=True)
    cleaned_chunks_excel_path = get_cleaned_chunks_excel_path(history_dir)
    if os.path.exists(cleaned_chunks_excel_path):
        rprint("[yellow]⚠️ Transcription results already exist, skipping transcription step.[/yellow]")
        return
    # step0 Convert video to audio
    video_files = [f for f in os.listdir(history_dir) if f.split('.')[-1].lower() in ['mp4','mov','avi','mkv','flv','wmv','webm']]
    if len(video_files) != 1:
        raise FileNotFoundError('Please upload exactly one video file to the history directory.')
    video_file = os.path.join(history_dir, video_files[0])
    convert_video_to_audio(video_file, history_dir)
    # step1 Demucs vocal separation:
    if load_key("demucs"):
        demucs_main(history_dir)
    # step2 Compress audio
    choose_audio = enhance_vocals(history_dir) if load_key("demucs") else get_raw_audio_file(history_dir)
    whisper_file = get_whisper_file(history_dir)
    whisper_audio = compress_audio(choose_audio, whisper_file)
    # step3 Extract audio
    segments = split_audio(whisper_audio, history_dir)
    # step4 Transcribe audio
    all_results = []
    for start, end in segments:
        result = transcribe_audio(whisper_audio, start, end)
        all_results.append(result)
    # step5 Combine results
    combined_result = {'segments': []}
    for result in all_results:
        combined_result['segments'].extend(result['segments'])
    # step6 Process df
    df = process_transcription(combined_result, history_dir)
    save_results(df, history_dir)
        
if __name__ == "__main__":
    transcribe()