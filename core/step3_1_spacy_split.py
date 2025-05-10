import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from spacy_utils.split_by_comma import split_by_comma_main
from spacy_utils.split_by_connector import split_sentences_main
from spacy_utils.split_by_mark import split_by_mark
from spacy_utils.split_long_by_root import split_long_by_root_main
from spacy_utils.load_nlp_model import init_nlp

def split_by_spacy(history_dir):
    log_dir = os.path.join(history_dir, 'log')
    os.makedirs(log_dir, exist_ok=True)
    splitbynlp_path = os.path.join(log_dir, 'sentence_splitbynlp.txt')
    if os.path.exists(splitbynlp_path):
        print(f"File '{splitbynlp_path}' already exists. Skipping split_by_spacy.")
        return
    nlp = init_nlp()
    split_by_mark(nlp, history_dir)
    split_by_comma_main(nlp, history_dir)
    split_sentences_main(nlp, history_dir)
    split_long_by_root_main(nlp, history_dir)
    return

if __name__ == '__main__':
    split_by_spacy()