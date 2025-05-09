import streamlit as st
import os, sys
from st_components.imports_and_utils import *
from core.config_utils import load_key

# SET PATH
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['PATH'] += os.pathsep + current_dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="VideoLingo", page_icon="docs/logo.svg")

SUB_VIDEO = "output/output_sub.mp4"
DUB_VIDEO = "output/output_dub.mp4"

def text_processing_section():
    st.header("Translate and Generate Subtitles")
    with st.container(border=True):
        st.markdown("""
        <p style='font-size: 20px;'>
        This stage includes the following steps:
        <p style='font-size: 20px;'>
            1. WhisperX word-level transcription<br>
            2. Sentence segmentation using NLP and LLM<br>
            3. Summarization and multi-step translation<br>
            4. Cutting and aligning long subtitles<br>
            5. Generating timeline and subtitles<br>
            6. Merging subtitles into the video
        """, unsafe_allow_html=True)

        # 新增本地视频上传入口
        uploaded_file = st.file_uploader("Upload a video file", type=["mp4","mov","avi","mkv","flv","wmv","webm"])
        if uploaded_file is not None:
            os.makedirs("output", exist_ok=True)
            video_path = os.path.join("output", uploaded_file.name)
            with open(video_path, "wb") as f:
                f.write(uploaded_file.read())
            st.success(f"Uploaded {uploaded_file.name} to output directory.")
            st.video(video_path)

        if not os.path.exists(SUB_VIDEO):
            if st.button("Start Processing Subtitles", key="text_processing_button"):
                process_text()
                st.rerun()
        else:
            if load_key("resolution") != "0x0":
                st.video(SUB_VIDEO)
            download_subtitle_zip_button(text="Download All Srt Files")
            
            if st.button("Archive to 'history'", key="cleanup_in_text_processing"):
                cleanup()
                st.rerun()

        # 新增清理output目录按钮
        if st.button("Clear Output Directory", key="clear_output_button"):
            for f in os.listdir("output"):
                file_path = os.path.join("output", f)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        import shutil
                        shutil.rmtree(file_path)
                except Exception as e:
                    st.warning(f"Failed to delete {file_path}: {e}")
            st.success("Output directory cleared. You can now upload a new video.")

        return True

def process_text():
    with st.spinner("Using Whisper for transcription..."):
        step2_whisperX.transcribe()
    with st.spinner("Splitting long sentences..."):  
        step3_1_spacy_split.split_by_spacy()
        step3_2_splitbymeaning.split_sentences_by_meaning()
    with st.spinner("Summarizing and translating..."):
        step4_1_summarize.get_summary()
        if load_key("pause_before_translate"):
            input("⚠️ PAUSE_BEFORE_TRANSLATE. Go to `output/log/terminology.json` to edit terminology. Then press ENTER to continue...")
        step4_2_translate_all.translate_all()
    with st.spinner("Processing and aligning subtitles..."): 
        step5_splitforsub.split_for_sub_main()
        step6_generate_final_timeline.align_timestamp_main()
    with st.spinner("Merging subtitles to video..."):
        step7_merge_sub_to_vid.merge_subtitles_to_video()
    
    st.success("Subtitle processing complete! 🎉")
    st.balloons()

def main():
    logo_col, _ = st.columns([1,1])
    with logo_col:
        st.image("docs/logo.png", use_column_width=True)
    st.markdown(button_style, unsafe_allow_html=True)
    st.markdown("<p style='font-size: 20px; color: #808080;'>Hello, welcome to VideoLingo. This project is currently under construction. If you encounter any issues, please feel free to ask questions on Github! You can also use VideoLingo on our website now: <a href='https://videolingo.io' target='_blank'>videolingo.io</a></p>", unsafe_allow_html=True)
    # add settings
    with st.sidebar:
        page_setting()
        st.markdown(give_star_button, unsafe_allow_html=True)
    text_processing_section()

if __name__ == "__main__":
    main()
