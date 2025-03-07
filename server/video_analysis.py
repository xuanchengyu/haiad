from moviepy.video.io. VideoFileClip import VideoFileClip
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from scenedetect import SceneManager, ContentDetector, open_video
import subprocess
import whisperx
import numpy as np
from openai import OpenAI
from PIL import Image
import base64
from io import BytesIO
import os
import traceback
import cv2
import glob

# 初始化OpenAI客户端
client = OpenAI(api_key="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")

# 视频处理相关函数
def scene_detection(video_path):
    try:
        # 使用 open_video 打开视频
        video = open_video(video_path)
        # 创建场景管理器
        scene_manager = SceneManager()
            
        # 添加内容检测器
        scene_manager.add_detector(
            ContentDetector(
                threshold=35.0,  # 场景切换敏感度
                min_scene_len=60  # 最小场景长度（帧数）
            )
        )
        # 检测场景
        scene_manager.detect_scenes(video)
        # 获取场景列表
        scene_list = scene_manager.get_scene_list()  
        return scene_list
    except Exception as e:
        print(f"Scene detection error: {str(e)}")
        traceback.print_exc()
        return []

def split_video(video_path, scene_list, output_dir):
    try:
        clip_paths = []
        # 验证输入视频
        if not os.path.exists(video_path):
            print(f"输入视频不存在: {video_path}")
            return []
            
        # 获取视频信息
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"无法打开视频: {video_path}")
            return []
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps
        cap.release()

        for i, scene in enumerate(scene_list):
            try:
                start_time = scene[0].get_seconds()
                end_time = scene[1].get_seconds()
                
                # 验证时间范围
                if start_time >= end_time or start_time < 0 or end_time > duration:
                    print(f"无效的时间范围: {start_time}-{end_time}, 跳过片段 {i+1}")
                    continue
                    
                # 确保片段至少有一帧
                if end_time - start_time < 1/fps:
                    print(f"片段 {i+1} 太短，跳过")
                    continue
                    
                clip_path = os.path.join(output_dir, f"clip_{i+1}.mp4")
                
                # 使用 FFmpeg 命令行直接分割视频
                command = [
                    'ffmpeg',
                    '-i', video_path,
                    '-ss', str(start_time),
                    '-t', str(end_time - start_time),
                    '-c', 'copy',  # 使用快速复制模式
                    '-avoid_negative_ts', '1',
                    '-y',  # 覆盖已存在的文件
                    clip_path
                ]
                
                result = subprocess.run(command, capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"分割片段 {i+1} 失败: {result.stderr}")
                    continue
                    
                # 验证生成的片段
                check_cap = cv2.VideoCapture(clip_path)
                if not check_cap.isOpened():
                    print(f"无法验证片段 {i+1}")
                    continue
                    
                clip_frames = int(check_cap.get(cv2.CAP_PROP_FRAME_COUNT))
                check_cap.release()
                
                if clip_frames > 0:
                    clip_paths.append(clip_path)
                else:
                    print(f"片段 {i+1} 没有有效帧")
                    if os.path.exists(clip_path):
                        os.remove(clip_path)
                        
            except Exception as e:
                print(f"处理片段 {i+1} 时出错: {str(e)}")
                continue
                
        return clip_paths
        
    except Exception as e:
        print(f"视频分割错误: {str(e)}")
        return []

def speech_recognition(video_path):
    try:
        model = whisperx.load_model("base", device="cpu", compute_type="float32")
        result = model.transcribe(video_path)
        return result["text"]    
    except Exception as e:
        print(f"Speech recognition error: {str(e)}")
        return "No transcription."

def sample_frames(video_clip, num_frames):
    try:
        total_frames = int(video_clip.fps * video_clip.duration)
        frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
        frames = [video_clip.get_frame(i / video_clip.fps) for i in frame_indices]
        return frames
    except Exception as e:
        print(f"Frame sampling error: {str(e)}")
        return []  
        

def convert_to_base64(image):
    try:
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"Image conversion error: {str(e)}")
        return ""

def generate_clip_descriptions(clip_paths, scenes, num_frames=2):
    try:
        descriptions = []
        for clip_path, scene in zip(clip_paths, scenes):
            clip = VideoFileClip(clip_path)
            frames = sample_frames(clip, num_frames)
            images = [Image.fromarray(frame) for frame in frames]
            image_files = [convert_to_base64(image) for image in images]
            
            content = []
            prompt = ("You are an expert in understanding scene transitions based on visual features in a video. "
                      "For the given sequence of images per timestamp, identify different scenes in the video. "
                      "Generate pure audio description for each scene with time ranges.\n"
                      f"{scene}"
            )
            
            content.append({"type": "text", "text": prompt})
            for image_file in image_files:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_file}"}
                })
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": content}],
                temperature=0,
                max_tokens=1000,
            )
            
            descriptions.append(response.choices[0].message.content)
            clip.close()
            
        return "".join(descriptions)
    except Exception as e:
        print(f"Generate clip description error: {str(e)}")
        return "Cannot generate scene description."

def generate_script(clip_descriptions):
    try:
        prompt = ("You are an expert at understanding audio descriptions of different scenes in a video. "
            "Generate a coherent and full audio description of each scene with non-overlapping time ranges. "
            "Keep as many scenes as possible covering all time ranges. "
            "Use character names wherever possible in the audio descriptions. "
            "Keep the audio description for each time range within one short sentence. "
            "Ensure the audio description do not overlap with original dialogues. \n\n"         
            "Please provide the audio description as a Python List of dictionaries, where each dictionary contains: \n"
            "scene_number (str), start_time (str, format: HH:MM:SS.mmm), end_time (str, format: HH:MM:SS.mmm), description (str). \n\n"
            "Please return the Python List of dictionaries as the final output and do not add any additional information. \n\n"
        )
        
        prompt += "\n\n".join(clip_descriptions)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10000
        )

        # 直接执行返回的 Python 代码
        script_text = response.choices[0].message.content
        print (script_text)
        
        # 如果返回的文本包含 Python 代码块标记，去除它
        if "```python" in script_text:
            script_text = script_text.split("```python")[1].split("```")[0].strip()
        elif "```" in script_text:
            script_text = script_text.split("```")[1].split("```")[0].strip()
        else:
            script_text = response.strip()
            
        print(script_text)
        script_array = eval(script_text)  # 直接执行 Python 代码返回数组
        print (script_array)
        return script_array
        
        # if not isinstance(script_array, list):
        #     raise ValueError("Response is not a list")
        
        # normalized_scenes = []
        # for i, scene in enumerate(script_array, 1):
        #     # 创建新的字典对象
        #     normalized_scene = dict()
                
        #     # 设置场景编号
        #     if isinstance(scene.get('scene_number'), str):
        #         try:
        #             scene_number = int(scene['scene_number'].split()[-1])
        #         except:
        #             scene_number = i
        #     else:
        #         scene_number = scene.get('scene_number', i)
                
        #     # 构建标准化的场景字典
        #     normalized_scene['scene_number'] = scene_number
        #     normalized_scene['start_time'] = scene.get('start_time')
        #     normalized_scene['end_time'] = scene.get('end_time')
        #     normalized_scene['description'] = scene.get('description')
                
        #     normalized_scenes.append(normalized_scene)
            
        # if not normalized_scenes:
        #     raise ValueError("No valid scenes found")
                
        # return normalized_scenes
    
    except Exception as e:
        print(f"Generate script error: {str(e)}")
        return [] 