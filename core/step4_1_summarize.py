import os, sys, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.ask_gpt import ask_gpt
from core.prompts_storage import get_summary_prompt
from core.config_utils import load_key
import pandas as pd

def get_terminology_json_path(history_dir):
    return os.path.join(history_dir, 'log', 'terminology.json')
def get_sentence_txt_path(history_dir):
    return os.path.join(history_dir, 'log', 'sentence_splitbymeaning.txt')
def get_custom_terms_path(history_dir):
    return os.path.join(history_dir, 'custom_terms.xlsx')

def combine_chunks(history_dir):
    """Combine the text chunks identified by whisper into a single long text"""
    with open(get_sentence_txt_path(history_dir), 'r', encoding='utf-8') as file:
        sentences = file.readlines()
    cleaned_sentences = [line.strip() for line in sentences]
    combined_text = ' '.join(cleaned_sentences)
    return combined_text[:load_key('summary_length')]  #! Return only the first x characters

def search_things_to_note_in_prompt(sentence, history_dir):
    """Search for terms to note in the given sentence"""
    with open(get_terminology_json_path(history_dir), 'r', encoding='utf-8') as file:
        things_to_note = json.load(file)
    things_to_note_list = [term['src'] for term in things_to_note['terms'] if term['src'].lower() in sentence.lower()]
    if things_to_note_list:
        prompt = '\n'.join(
            f'{i+1}. "{term["src"]}": "{term["tgt"]}",'
            f' meaning: {term["note"]}'
            for i, term in enumerate(things_to_note['terms'])
            if term['src'] in things_to_note_list
        )
        return prompt
    else:
        return None

def get_summary(history_dir):
    src_content = combine_chunks(history_dir)
    # 如果内容极短，直接返回空摘要和术语，避免异常
    if len(src_content.strip()) < 10:
        summary = {
            "topic": "",
            "terms": []
        }
        with open(get_terminology_json_path(history_dir), 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=4)
        print(f'⚠️ Source too short, skipped summary & terminology extraction. Saved empty result to → `{get_terminology_json_path(history_dir)}`')
        return summary
    custom_terms_path = get_custom_terms_path(history_dir)
    if os.path.exists(custom_terms_path):
        custom_terms = pd.read_excel(custom_terms_path)
        custom_terms_json = {
            "terms": [
                {
                    "src": str(row.iloc[0]),
                    "tgt": str(row.iloc[1]),
                    "note": str(row.iloc[2])
                }
                for _, row in custom_terms.iterrows()
            ]
        }
        if len(custom_terms) > 0:
            print(f"📖 Custom Terms Loaded: {len(custom_terms)} terms")
            print("📝 Terms Content:", json.dumps(custom_terms_json, indent=2, ensure_ascii=False))
    else:
        custom_terms_json = {"terms": []}
        print("[yellow]No custom_terms.xlsx found, proceeding with empty custom terms.[/yellow]")
    summary_prompt = get_summary_prompt(src_content, custom_terms_json)
    print("📝 Summarizing and extracting terminology ...")
    
    def valid_summary(response_data):
        required_keys = {'src', 'tgt', 'note'}
        if 'terms' not in response_data:
            return {"status": "error", "message": "Invalid response format"}
        for term in response_data['terms']:
            if not all(key in term for key in required_keys):
                return {"status": "error", "message": "Invalid response format"}   
        return {"status": "success", "message": "Summary completed"}

    summary = ask_gpt(summary_prompt, response_json=True, valid_def=valid_summary, log_title='summary')
    if 'terms' in summary:
        summary['terms'].extend(custom_terms_json['terms'])
    
    with open(get_terminology_json_path(history_dir), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=4)

    print(f'💾 Summary log saved to → `{get_terminology_json_path(history_dir)}`')

if __name__ == '__main__':
    get_summary()