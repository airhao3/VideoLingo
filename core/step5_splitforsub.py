import sys, os
import pandas as pd
from typing import List, Tuple
import concurrent.futures
import cv2
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.step3_2_splitbymeaning import split_sentence
from core.ask_gpt import ask_gpt
from core.prompts_storage import get_align_prompt
from core.config_utils import load_key, get_joiner
from core.step1_ytdlp import find_video_files
from rich.panel import Panel
from rich.console import Console
from rich.table import Table

console = Console()

# Constants
INPUT_FILE = "output/log/translation_results.xlsx"
OUTPUT_SPLIT_FILE = "output/log/translation_results_for_subtitles.xlsx"
OUTPUT_REMERGED_FILE = "output/log/translation_results_remerged.xlsx"

# ! You can modify your own weights here
# Chinese and Japanese 2.5 characters, Korean 2 characters, Thai 1.5 characters, full-width symbols 2 characters, other English-based and half-width symbols 1 character
def calc_len(text: str) -> float:
    text = str(text) # force convert
    def char_weight(char):
        code = ord(char)
        if 0x4E00 <= code <= 0x9FFF or 0x3040 <= code <= 0x30FF:  # Chinese and Japanese
            return 1.75
        elif 0xAC00 <= code <= 0xD7A3 or 0x1100 <= code <= 0x11FF:  # Korean
            return 1.5
        elif 0x0E00 <= code <= 0x0E7F:  # Thai
            return 1
        elif 0xFF01 <= code <= 0xFF5E:  # full-width symbols
            return 1.75
        else:  # other characters (e.g. English and half-width symbols)
            return 1

    return sum(char_weight(char) for char in text)

def align_subs(src_sub: str, tr_sub: str, src_part: str) -> Tuple[List[str], List[str], str]:
    align_prompt = get_align_prompt(src_sub, tr_sub, src_part)
    
    def valid_align(response_data):
        if 'align' not in response_data:
            return {"status": "error", "message": "Missing required key: `align`"}
        if len(response_data['align']) < 2:
            return {"status": "error", "message": "Align does not contain more than 1 part as expected!"}
        return {"status": "success", "message": "Align completed"}

    parsed = ask_gpt(align_prompt, response_json=True, valid_def=valid_align, log_title='align_subs')
    
    align_data = parsed['align']
    src_parts = src_part.split('\n')
    tr_parts = [item[f'target_part_{i+1}'].strip() for i, item in enumerate(align_data)]
    
    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == 'auto' else whisper_language
    joiner = get_joiner(language)
    tr_remerged = joiner.join(tr_parts)
    
    table = Table(title="🔗 Aligned parts")
    table.add_column("Language", style="cyan")
    table.add_column("Parts", style="magenta")
    table.add_row("SRC_LANG", "\n".join(src_parts))
    table.add_row("TARGET_LANG", "\n".join(tr_parts))
    table.add_row("REMERGED", tr_remerged)
    console.print(table)
    
    return src_parts, tr_parts, tr_remerged

def get_video_dimensions():
    """Get video dimensions and calculate max subtitle length"""
    video_file = find_video_files()
    cap = cv2.VideoCapture(video_file)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    
    is_vertical = height > width
    aspect_ratio = min(width, height) / max(width, height)
    
    # Calculate base subtitle length based on video width
    base_length = width / 15  # Approximate character width
    
    # Adjust length based on orientation
    if is_vertical:
        max_length = int(base_length * 0.6)  # Shorter lines for vertical videos
    else:
        max_length = int(base_length * 0.8)  # Longer lines for horizontal videos
    
    # Adjust based on aspect ratio (narrower videos get shorter lines)
    max_length = int(max_length * (0.8 + 0.2 * aspect_ratio))
    
    return max_length

def split_align_subs(src_lines: List[str], tr_lines: List[str]) -> Tuple[List[str], List[str], List[str]]:
    subtitle_set = load_key("subtitle")
    MAX_SUB_LENGTH = get_video_dimensions()
    TARGET_SUB_MULTIPLIER = subtitle_set["target_multiplier"]
    
    # Make copies of input lists
    src_lines = [str(s) for s in src_lines]
    tr_lines = [str(t) for t in tr_lines]
    
    console.print(f"[cyan]ℹ Using dynamic subtitle length: {MAX_SUB_LENGTH} characters[/cyan]")
    
    to_split = []
    for i, (src, tr) in enumerate(zip(src_lines, tr_lines)):
        if len(src) > MAX_SUB_LENGTH or calc_len(tr) * TARGET_SUB_MULTIPLIER > MAX_SUB_LENGTH:
            to_split.append(i)
            table = Table(title=f"📏 Line {i} needs to be split")
            table.add_column("Type", style="cyan")
            table.add_column("Content", style="magenta")
            table.add_row("Source Line", src)
            table.add_row("Target Line", tr)
            console.print(table)
    
    # Process each line that needs splitting
    split_indices = {}
    for i in to_split:
        try:
            split_src = split_sentence(src_lines[i], num_parts=2).strip()
            src_parts, tr_parts, tr_remerged = align_subs(src_lines[i], tr_lines[i], split_src)
            
            # Ensure we got valid results
            if not src_parts or not tr_parts:
                console.print(f"[yellow]⚠️ Warning: Empty split result for line {i}, keeping original[/yellow]")
                continue
            
            # Ensure lengths match
            if len(src_parts) != len(tr_parts):
                console.print(f"[yellow]⚠️ Warning: Mismatched split lengths for line {i}, keeping original[/yellow]")
                continue
            
            # Store split results and index
            split_indices[i] = len(src_parts)
            src_lines[i] = src_parts
            tr_lines[i] = tr_parts
            
        except Exception as e:
            console.print(f"[red]❌ Error processing line {i}: {str(e)}[/red]")
    
    # Create new lists with split content
    final_src = []
    final_tr = []
    final_remerged = []
    
    # First pass: extend final_src and final_tr with split lines
    for i in range(len(src_lines)):
        if i in split_indices:
            # This line was split
            if isinstance(src_lines[i], (list, tuple)):
                final_src.extend(str(s) for s in src_lines[i])
                final_tr.extend(str(t) for t in tr_lines[i])
        else:
            # This line wasn't split
            final_src.append(str(src_lines[i]))
            final_tr.append(str(tr_lines[i]))
    
    # Second pass: create remerged list with same length as split lists
    for i in range(len(final_src)):
        # Add empty lines for split parts to maintain alignment
        final_remerged.append(str(tr_lines[i // 2 if i % 2 == 1 else i // 2]))
    
    # Verify lengths match
    lengths = {
        'src': len(final_src),
        'tr': len(final_tr),
        'remerged': len(final_remerged)
    }
    if not (lengths['src'] == lengths['tr'] == lengths['remerged']):
        console.print(f"[red]❌ Error: Final lengths don't match: {lengths}[/red]")
        # Return original lists if lengths don't match
        return src_lines, tr_lines, tr_lines
    
    return final_src, final_tr, final_remerged
    
    return src_lines, tr_lines, remerged_tr_lines

def split_for_sub_main():
    console.print("[bold green]🚀 Start splitting subtitles...[/bold green]")
    
    try:
        df = pd.read_excel(INPUT_FILE)
        src = df['Source'].tolist()
        trans = df['Translation'].tolist()
        
        # Ensure input lists are valid
        if len(src) != len(trans):
            raise ValueError(f"Input lists have different lengths: src={len(src)}, trans={len(trans)}")
        
        # Get dynamic subtitle length based on video dimensions
        MAX_SUB_LENGTH = get_video_dimensions()
        subtitle_set = load_key("subtitle")
        TARGET_SUB_MULTIPLIER = subtitle_set["target_multiplier"]
        
        console.print(f"[cyan]ℹ Using dynamic subtitle length: {MAX_SUB_LENGTH} characters[/cyan]")
        
        # Initialize best results
        best_split_src = None
        best_split_trans = None
        best_remerged = None
        best_max_length = float('inf')
        
        for attempt in range(3):  # 使用固定的3次重试
            console.print(Panel(f"🔄 Split attempt {attempt + 1}", expand=False))
            
            # Make copies to prevent modifying original data
            split_src, split_trans, remerged = split_align_subs(list(src), list(trans))
            
            # Skip if lengths don't match
            if len(split_src) != len(split_trans):
                console.print(f"[yellow]⚠️ Warning: Split results have different lengths on attempt {attempt + 1}[/yellow]")
                continue
            
            # Calculate maximum length
            max_src_len = max(len(s) for s in split_src)
            max_tr_len = max(calc_len(t) * TARGET_SUB_MULTIPLIER for t in split_trans)
            current_max_length = max(max_src_len, max_tr_len)
            
            # Update best results if this attempt is better
            if current_max_length < best_max_length:
                best_max_length = current_max_length
                best_split_src = split_src
                best_split_trans = split_trans
                best_remerged = remerged
            
            # Break if all subtitles meet length requirements
            if all(len(s) <= MAX_SUB_LENGTH for s in split_src) and \
               all(calc_len(t) * TARGET_SUB_MULTIPLIER <= MAX_SUB_LENGTH for t in split_trans):
                break
        
        # Use best results or raise error if none found
        if best_split_src is None:
            raise ValueError("Failed to find valid split solution after all attempts")
        
        # Final length verification
        if len(best_split_src) != len(best_split_trans) or len(best_split_src) != len(best_remerged):
            lengths = {
                'split_src': len(best_split_src),
                'split_trans': len(best_split_trans),
                'remerged': len(best_remerged)
            }
            raise ValueError(f"Final lengths don't match: {lengths}")
        
        # Save results
        pd.DataFrame({
            'Source': best_split_src,
            'Translation': best_split_trans
        }).to_excel(OUTPUT_SPLIT_FILE, index=False)
        
        pd.DataFrame({
            'Source': best_split_src,
            'Translation': best_remerged
        }).to_excel(OUTPUT_REMERGED_FILE, index=False)
        
        console.print("[bold green]✅ Subtitle splitting completed successfully![/bold green]")
        console.print(f"[cyan]ℹ Final statistics:[/cyan]")
        console.print(f"  - Original lines: {len(src)}")
        console.print(f"  - Split lines: {len(best_split_src)}")
        console.print(f"  - Maximum source length: {max(len(s) for s in best_split_src)}")
        console.print(f"  - Maximum translation length: {max(calc_len(t) for t in best_split_trans)}")
        
    except Exception as e:
        console.print(f"[bold red]❌ Error during subtitle splitting: {str(e)}[/bold red]")
        raise

if __name__ == '__main__':
    split_for_sub_main()
