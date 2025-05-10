import streamlit as st
import os, sys
from st_components.imports_and_utils import *
from core.config_utils import load_key

# SET PATH
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['PATH'] += os.pathsep + current_dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="VideoLingo", page_icon="docs/logo.svg")

import uuid

# 生成唯一 video_id（每次上传新视频时调用）
def generate_video_id():
    return uuid.uuid4().hex[:12]

# 当前 session 的 video_id，初始为空
if 'video_id' not in st.session_state:
    st.session_state['video_id'] = ''

def get_history_dir():
    return os.path.join('history', st.session_state['video_id'])

def get_video_path(filename):
    return os.path.join(get_history_dir(), filename)

SUB_VIDEO = lambda: get_video_path("output_sub.mp4")
DUB_VIDEO = lambda: get_video_path("output_dub.mp4")

def text_processing_section():
    st.header("Translate and Generate Subtitles")
    with st.container(border=True):
        # 字幕位置参数调节UI
        import yaml
        config_path = 'config.yaml'
        try:
            with open(config_path, 'r') as f:
                cfg = yaml.safe_load(f)
        except Exception:
            cfg = {}
        margin_v = cfg.get('subtitle', {}).get('margin_v', {
            'src': {'vertical': 200, 'horizontal': 54},
            'trans': {'vertical': 100, 'horizontal': 27}
        })
        st.markdown('#### Subtitle Vertical Margin (像素)')
        c1, c2 = st.columns(2)
        with c1:
            src_v = st.number_input('原文字幕竖屏边距', min_value=0, max_value=800, value=margin_v['src'].get('vertical', 200), key='src_v')
            src_h = st.number_input('原文字幕横屏边距', min_value=0, max_value=400, value=margin_v['src'].get('horizontal', 54), key='src_h')
        with c2:
            trans_v = st.number_input('译文字幕竖屏边距', min_value=0, max_value=800, value=margin_v['trans'].get('vertical', 100), key='trans_v')
            trans_h = st.number_input('译文字幕横屏边距', min_value=0, max_value=400, value=margin_v['trans'].get('horizontal', 27), key='trans_h')
        if st.button('保存字幕边距设置'):
            cfg.setdefault('subtitle', {}).setdefault('margin_v', {})
            cfg['subtitle']['margin_v'] = {
                'src': {'vertical': src_v, 'horizontal': src_h},
                'trans': {'vertical': trans_v, 'horizontal': trans_h}
            }
            with open(config_path, 'w') as f:
                yaml.dump(cfg, f, allow_unicode=True)
            st.success('字幕边距设置已保存！')


        # 新增本地视频上传入口
        uploaded_file = st.file_uploader(
    "Upload a video file",
    type=["mp4","mov","avi","mkv","flv","wmv","webm"],
    key=f"file_uploader_{st.session_state['video_id']}"
)
        if uploaded_file is not None:
            import hashlib, json
            # 保存到临时路径
            tmp_path = os.path.join("/tmp", uploaded_file.name)
            with open(tmp_path, "wb") as f:
                f.write(uploaded_file.read())
            # 计算md5
            def calc_md5(path):
                with open(path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()
            video_md5 = calc_md5(tmp_path)
            # 加载/更新索引
            idx_path = os.path.join("history", "video_index.json")
            if os.path.exists(idx_path):
                with open(idx_path) as f:
                    video_index = json.load(f)
            else:
                video_index = {}
            if video_md5 in video_index:
                prev_session = video_index[video_md5]
                st.success(f"该视频已上传过，历史 session: {prev_session}。已为你显示历史处理结果。")
                prev_history_dir = os.path.join("history", prev_session)
                prev_sub_video = os.path.join(prev_history_dir, "output_sub.mp4")
                if os.path.exists(prev_sub_video):
                    st.video(prev_sub_video)
                else:
                    st.info("历史 session 尚未生成字幕视频。")
                # 下载字幕按钮（直接用历史目录）
                prev_srt_files = [f for f in os.listdir(prev_history_dir) if f.endswith('.srt')]
                import io, zipfile
                if prev_srt_files:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                        for file_name in prev_srt_files:
                            file_path = os.path.join(prev_history_dir, file_name)
                            with open(file_path, "rb") as file:
                                zip_file.writestr(file_name, file.read())
                    zip_buffer.seek(0)
                    st.download_button(
                        label="Download All Srt Files",
                        data=zip_buffer,
                        file_name="subtitles.zip",
                        mime="application/zip"
                    )
                else:
                    st.info("历史 session 暂无字幕文件。")
            else:
                # 新建唯一 session id
                st.session_state['video_id'] = generate_video_id()
                history_dir = get_history_dir()
                os.makedirs(history_dir, exist_ok=True)
                video_path = os.path.join(history_dir, uploaded_file.name)
                # 移动临时文件到 session 目录
                import shutil
                shutil.move(tmp_path, video_path)
                st.success(f"Uploaded {uploaded_file.name} to history/{st.session_state['video_id']} directory.")
                st.video(video_path)
                st.session_state['uploaded_video_path'] = video_path
                # 登记索引
                video_index[video_md5] = st.session_state['video_id']
                with open(idx_path, "w") as f:
                    json.dump(video_index, f)

        # 检查是否已生成字幕视频，并确保有且仅有一个视频文件
        history_dir = get_history_dir()
        if os.path.exists(history_dir):
            video_files = [f for f in os.listdir(history_dir) if f.split('.')[-1].lower() in ['mp4','mov','avi','mkv','flv','wmv','webm']]
        else:
            video_files = []
        if not os.path.exists(SUB_VIDEO()) and len(video_files) == 1:
            if st.button("Start Processing Subtitles", key="text_processing_button"):
                process_text(history_dir)
                st.rerun()
        elif not os.path.exists(SUB_VIDEO()) and len(video_files) != 1:
            st.info("请上传一个视频文件后再开始处理字幕。")
        else:
            if load_key("resolution") != "0x0":
                video_path = SUB_VIDEO()
                if os.path.exists(video_path):
                    st.video(video_path)
            download_subtitle_zip_button(text="Download All Srt Files")
        # session 切换（新建/重置）按钮
        if st.button("New Session / Reset", key="new_session_button"):
            # 先生成新 video_id
            new_id = generate_video_id()
            # 清空所有 session_state
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.session_state['video_id'] = new_id
            # 清理新 session 目录下所有视频
            history_dir = os.path.join('history', new_id)
            if os.path.exists(history_dir):
                for f in os.listdir(history_dir):
                    if f.split('.')[-1].lower() in ['mp4','mov','avi','mkv','flv','wmv','webm']:
                        os.remove(os.path.join(history_dir, f))
            st.rerun()
        return True

def process_text(history_dir):
    with st.spinner("Using Whisper for transcription..."):
        step2_whisperX.transcribe(history_dir)
    with st.spinner("Splitting long sentences..."):
        step3_1_spacy_split.split_by_spacy(history_dir)
        step3_2_splitbymeaning.split_sentences_by_meaning(history_dir)
    with st.spinner("Summarizing and translating..."):
        step4_1_summarize.get_summary(history_dir)
        if load_key("pause_before_translate"):
            input(f"⚠️ PAUSE_BEFORE_TRANSLATE. Go to `{history_dir}/log/terminology.json` to edit terminology. Then press ENTER to continue...")
        step4_2_translate_all.translate_all(history_dir)
    with st.spinner("Processing and aligning subtitles..."):

        step5_splitforsub.split_for_sub_main(history_dir)
        step6_generate_final_timeline.align_timestamp_main(history_dir)
    with st.spinner("Merging subtitles to video..."):
        step7_merge_sub_to_vid.merge_subtitles_to_video(history_dir)
    
    st.success("Subtitle processing complete! 🎉")
    st.balloons()

def main():

    st.markdown(button_style, unsafe_allow_html=True)
    st.markdown("<p style='font-size: 20px; color: #808080;'>Hello, welcome to VideoLingo. This project is currently under construction. If you encounter any issues, please feel free to ask questions on Github! You can also use VideoLingo on our website now: <a href='https://videolingo.io' target='_blank'>videolingo.io</a></p>", unsafe_allow_html=True)
    # add settings
    with st.sidebar:
        page_setting()
        st.markdown(give_star_button, unsafe_allow_html=True)
    text_processing_section()

if __name__ == "__main__":
    main()
