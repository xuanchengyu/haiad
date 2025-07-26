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
import requests  # 新增导入
import ssl
from urllib3.util.ssl_ import create_urllib3_context
from urllib3.util.retry import Retry
from datetime import datetime
import time

import certifi
from requests.adapters import HTTPAdapter
# 初始化OpenAI客户端
client = OpenAI(api_key="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")


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


def split_video_segment(video_path, start_time, end_time, output_dir):
    try:
        # 验证输入视频
        if not os.path.exists(video_path):
            print(f"输入视频不存在: {video_path}")
            return None
            
        # 获取视频信息
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"无法打开视频: {video_path}")
            return None
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps
        cap.release()
        
        # 确保时间参数是字符串
        start_time_str = str(start_time) if not isinstance(start_time, tuple) else str(start_time[0])
        end_time_str = str(end_time) if not isinstance(end_time, tuple) else str(end_time[0])

        time_duration = time_diff(start_time_str, end_time_str)
        print("时间差", time_duration)
        print("时间差的类型", type(time_duration))
        clip_path = os.path.join(output_dir, f"clip_{start_time_str}_{end_time_str}.mp4")
        
        # 使用 FFmpeg 命令行直接分割视频
        command = [
            'ffmpeg',
            '-ss', start_time_str,
            '-i', video_path,
            '-t', str(time_duration),
            '-vf', 'fps=25',  # 按原视频帧率设置
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '28',
            '-c:a', 'aac',
            '-y',
            clip_path
        ]

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print("FFmpeg error:", result.stderr)
            return None
        else:
            print("Clip created:", clip_path)
            return clip_path
    except Exception as e:
        print(f"Split video segment error: {str(e)}")
        return None

    # def decide_num_frames(clip_path, start_time, end_time, interval_sec=5, max_frames=10):
    #     duration = time_diff(start_time, end_time)
    #     num = int(duration / interval_sec)
    #     num_frames = min(max(1, num), max_frames)
    #     return num_frames

# 1. 用AI生成音频描述
# 杨瑞霞修改代码
def generate_clip_description(clip_path, creativity, max_retries=100, video_context=""):
    def call_with_limit(content, max_retries):
        attempt = 0
        while attempt < max_retries:
            try:
                # 将前端的0-10范围转换为OpenAI API的0-2范围
                temperature = min(2.0, max(0.0, creativity / 5.0))
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": content}],
                    temperature=temperature,
                    max_tokens=10000,
                )
                message = response.choices[0].message.content
                if message:
                    return message
                else:
                    raise ValueError("Empty response content.")
            except Exception as e:
                attempt += 1
                print(f"[Retry {attempt}/{max_retries}] Error: {str(e)}")
        raise RuntimeError("Exceeded maximum retry limit.")

    try:
        descriptions = []
        clip = VideoFileClip(clip_path)
        # 使用场景检测的关键帧提取（无需指定帧数）
        frames = scene_based_keyframe_extraction(clip)
        images = [Image.fromarray(frame) for frame in frames]
        image_files = [convert_to_base64(image) for image in images]

        content = []
        
        # 基础prompt
        prompt = (
            "You are an expert in understanding scene transitions based on visual features in a video. "
            "Given a sequence of video keyframes with timestamps, identify different scenes in the video. "
            "For each identified scene, provide a pure audio description in one short sentence. "
            "Only describe what you can actually see in the frames. Avoid subjective analysis.\n\n"
        )
        
        # 如果有视频背景信息，添加到prompt中
        if video_context:
            prompt += f"Video Context: {video_context}\n\n"
        
        prompt += (
            "Please return the description for each scene as a Python List of dictionaries, where each dictionary contains: \n"
            "{time_range (str), description (str)}\n\n"
            "Please return the Python List of dictionaries as the final output and do not add any additional information. \n\n"
        )

        content.append({"type": "text", "text": prompt})
        for image_file in image_files:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_file}"}
            })

        description = call_with_limit(content, max_retries)
        descriptions.append(description)
        clip.close()
        return "".join(descriptions)

    except Exception as e:
        print(f"Generate clip description error: {str(e)}")
        return "Cannot generate scene description."


# 2.1 用AI根据音频描述，生成五条最终描述(Request AI description页面)
# 杨瑞霞修改代码
def generate_script_2(clip_descriptions, max_retries=100):
    def call_with_retry(prompt, max_retries):
        attempt = 0
        while attempt < max_retries:
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=10000
                )
                script_text = response.choices[0].message.content
                print("Raw response:\n", script_text)

                # 去除 ```python ``` 或 ``` 标记
                if "```python" in script_text:
                    script_text = script_text.split("```python")[1].split("```")[0].strip()
                elif "```" in script_text:
                    script_text = script_text.split("```")[1].split("```")[0].strip()

                # 解析为 Python 对象
                script_array = eval(script_text)

                # 检查是否为 list 且包含 dict
                if isinstance(script_array, list) and all(isinstance(item, dict) for item in script_array):
                    return script_array
                else:
                    raise ValueError("Response is not a valid list of dictionaries")

            except Exception as e:
                attempt += 1
                print(f"[Retry {attempt}/{max_retries}] Error: {str(e)}")

        raise RuntimeError("Exceeded maximum retry attempts for script generation.")

    try:
        # prompt = (
        #     "You are an expert at understanding audio descriptions of different scenes in a video. "
        #     "Please generate five full audio descriptions of the scene in different styles for the following scene "
        #     "and keep each audio description within one short sentence. "
        #     "And provide the five different audio descriptions as a Python List of dictionaries, where each dictionary contains: \n"
        #     "{description_number (str), start_time (str, format: HH:MM:SS.mmm), end_time (str, format: HH:MM:SS.mmm), description (str)} \n\n"
        #     "Please return the Python List of dictionaries as the final output and do not add any additional information. \n\n"
        # )
        # prompt = ("You are an expert at understanding audio descriptions of different scenes in a video. "
        #     "Generate a coherent and full audio description of each scene with non-overlapping time ranges. "
        #     "Keep as many scenes as possible covering all time ranges. "
        #     "Use character names wherever possible in the audio descriptions. "
        #     "Keep the audio description for each time range within one short sentence. "
        #     "Ensure the audio description do not overlap with original dialogues. \n\n"
        # )
        prompt = (
            "You are an expert at writing audio descriptions (AD) for video clips. "
            
            "Below is a list of short AD snippets covering different time ranges within the same video clip. "
            "Your task is to synthesize and generate a full and coherent AD of the entire clip, in 3 different writing styles.\n\n"

            "The three styles are:\n"
            "1. Objective - factual and straightforward\n"
            "2. Descriptive - detailed and vivid\n"
            "3. Child-Friendly - simple and easy to understand\n\n"
            
            "For each style, return a well-structured description composed of several short sentences. "
            "Focus on key actions and objects. Avoid subjective analysis. "
            "Do not include any special characters, code formatting, or non-English text.\n\n"

            "Please return the 3 audio descriptions as a Python List of dictionaries, where each dictionary contains: \n"
            "{description_number (str), description (str)}\n\n"
            "Please return the Python List of dictionaries as the final output and do not add any additional information. \n\n"
    )


        # prompt = (
        #     "You are an expert at understanding audio descriptions of different scenes in a video."
        #     "Based on the given content, please generate a coherent and full audio descriptions in 5 distinct writing styles. "
        #     "Keep as many scenes as possible covering all time ranges. "
        #     "Keep the audio description for each time range within one short sentence. "
        #     "Each description should be a clear, well-structured paragraph in English only. "
            
        #     "The five styles are:\n"
        #     "1. Objective.\n"
        #     "2. Descriptive.\n"
        #     "3. Conversational and Informal.\n"
        #     "4. Interpretive.\n"
        #     "5. Child-Friendly and Simplified.\n\n"
            
        #     "Please return the five audio descriptions as a Python List of dictionaries, where each dictionary contains: \n"
        #     "{description_number (str), description (str)}\n\n"
        #     "Please return the Python List of dictionaries as the final output and do not add any additional information. \n\n"
        # )

        prompt += "\n\n".join(clip_descriptions)

        return call_with_retry(prompt, max_retries)

    except Exception as e:
        print(f"Generate script error: {str(e)}")
        return []

def time_diff(start_str, end_str):
    """
    计算两个时间字符串的差值，返回 FFmpeg 兼容的 HH:MM:SS.mmm 格式
    参数示例：
        start_str = "00:00:01.001"
        end_str   = "00:00:02.000"
    返回："00:00:00.999"
    """
    try:
        # Ensure inputs are strings
        print("开始时间原始:",start_str)
        print("开始时间原始类型:",type(start_str))
        start_str = str(start_str)
        end_str = str(end_str)
        print("开始时间:",start_str)
        print("开始时间类型:",type(start_str))
        # 解析时间字符串（支持毫秒）
        fmt = "%H:%M:%S.%f"
        start = datetime.strptime(start_str, fmt)
        end = datetime.strptime(end_str, fmt)
        
        # 计算时间差（微秒级）
        delta = end - start
        total_microseconds = delta.total_seconds() * 1_000_000
        
        # 转换为时分秒毫秒格式 
        hours, rem = divmod(total_microseconds, 3_600_000_000)
        minutes, rem = divmod(rem, 60_000_000)
        seconds, milliseconds = divmod(rem, 1_000_000)
        
        # 处理边界条件（负时间差）
        if total_microseconds < 0:
            return "00:00:00.000"
        
        # 格式化为 FFmpeg 兼容的时间字符串 
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}.{int(milliseconds//1000):03}"
    
    except ValueError as e:
        print(f"时间格式错误: {str(e)}")
        return "00:00:00.000"


        
# 2.2 用AI根据音频描述，生成五条最终描述(Giving your instructions页面)
# 杨瑞霞修改代码
def generate_script_with_instruction(clip_descriptions, selected_keywords, additional_instructions, max_retries=100):
    def call_with_retry(prompt, max_retries):
        attempt = 0
        while attempt < max_retries:
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=10000
                )
                script_text = response.choices[0].message.content
                print("Raw response:\n", script_text)

                # 清理代码块标记
                if "```python" in script_text:
                    script_text = script_text.split("```python")[1].split("```")[0].strip()
                elif "```" in script_text:
                    script_text = script_text.split("```")[1].split("```")[0].strip()

                # 尝试 eval
                script_array = eval(script_text)

                if isinstance(script_array, list) and all(isinstance(item, dict) for item in script_array):
                    return script_array
                else:
                    raise ValueError("Response is not a valid list of dictionaries")

            except Exception as e:
                attempt += 1
                print(f"[Retry {attempt}/{max_retries}] Error: {str(e)}")

        raise RuntimeError("Exceeded maximum retry attempts.")

    try:
        # 构建 prompt
        # prompt = (
        #     "You are an expert at understanding audio descriptions of different scenes in a video. "
        #     "Please generate five full audio descriptions of the scene in different styles for the following scene "
        #     "and keep each audio description within one short sentence. "
        #     "And provide the five different audio descriptions as a Python List of dictionaries, where each dictionary contains: \n"
        #     "{description_number (str), start_time (str, format: HH:MM:SS.mmm), end_time (str, format: HH:MM:SS.mmm), description (str)} \n\n"
        #     "Please return the Python List of dictionaries as the final output and do not add any additional information.\n\n"
        # )

        prompt = (
            "You are an expert in writing high-quality audio descriptions (AD) for video clips. "

            "Below is a list of short AD snippets covering different time ranges within the same video clip. "
            "Your task is to synthesize and generate a full and coherent AD of the entire clip.\n\n"

            "You should rewrite them in 3 different versions based on the user-defined style and insructions."
            "For each version, return a well-structured description composed of several short sentences. "
            "Focus on key actions and objects. Avoid subjective analysis. "
            "Do not include any special characters, code formatting, or non-English text.\n\n"

            "Please return the 3 versions ofaudio descriptions as a Python List of dictionaries, where each dictionary contains: \n"
            "{description_number (str), description (str)}\n\n"
            "Please return the Python List of dictionaries as the final output and do not add any additional information. \n\n"
    )
        
        
        prompt += "\n\n".join(clip_descriptions)
        if selected_keywords:
            prompt += "\n\nThe user-defined style should be:\n" + ", ".join(selected_keywords)
        if additional_instructions:
            prompt += "\n\nPlease also follow these additional requirements:\n" + "\n".join(additional_instructions)

        return call_with_retry(prompt, max_retries)

    except Exception as e:
        print(f"Generate script error: {str(e)}")
        return []


# def calculate_dynamic_frames(duration_seconds):
#     """
#     动态计算抽帧数量 - 每3秒1帧，无差别处理
#     """
#     duration = int(duration_seconds)
    
#     # 基础配置
#     min_frames = 2
#     max_frames = 60
    
#     # 处理不足3秒的情况
#     if duration < 3:
#         # 不足3秒的视频，至少抽2帧
#         frames = min_frames
#     else:
#         # 每3秒1帧，无差别处理
#         frames = duration // 3
    
#     # 确保不超过最大帧数
#     return min(frames, max_frames)

# def frame_number(start_str, end_str):
#     """
#     计算两个时间字符串的差值，返回 FFmpeg 兼容的 HH:MM:SS.mmm 格式
#     参数示例：
#         start_str = "00:00:01.001"
#         end_str   = "00:00:02.000"
#     返回："00:00:00.999"
#     """
#     try:
#         # Ensure inputs are strings
#         print("开始时间原始:",start_str)
#         print("开始时间原始类型:",type(start_str))
#         start_str = str(start_str)
#         end_str = str(end_str)
#         print("开始时间:",start_str)
#         print("开始时间类型:",type(start_str))
#         # 解析时间字符串（支持毫秒）
#         fmt = "%H:%M:%S.%f"
#         start = datetime.strptime(start_str, fmt)
#         end = datetime.strptime(end_str, fmt)
        
#         # 计算时间差（微秒级）
#         delta = end - start
#         total_microseconds = delta.total_seconds() * 1_000_000
#         seconds_tuple = divmod(total_microseconds, 1_000_000)
#         seconds = seconds_tuple[0]  # 只取秒数部分
        
#         # 使用动态计算
#         num_frames = calculate_dynamic_frames(seconds)
#         print(f"视频时长: {seconds}秒, 抽帧数: {num_frames}")
#         return num_frames
    
#     except ValueError as e:
#         # print(f"时间格式错误: {str(e)}")
#         return 2

def scene_based_keyframe_extraction(video_clip):
    """
    基于场景检测的关键帧提取 - 完全基于场景变化
    """
    try:
        total_frames = int(video_clip.fps * video_clip.duration)
        
        # 检测场景变化点
        scene_changes = detect_scene_changes_advanced(video_clip)
        
        # 如果没有检测到场景变化，使用基础采样
        if not scene_changes:
            print("No scene changes detected, using basic sampling")
            # 根据视频长度决定采样数量
            if total_frames <= 100:
                num_frames = 2
            elif total_frames <= 500:
                num_frames = 4
            else:
                num_frames = 6
            return sample_frames(video_clip, num_frames)
        
        # 保留所有检测到的场景变化，不限制数量
        print(f"Using all {len(scene_changes)} detected scene changes")
        
        # 基于场景变化点选择关键帧
        keyframes = select_key_frames(video_clip, scene_changes)
        
        # 限制总帧数，避免过多
        max_frames = 15  # 从10增加到15，允许更多帧
        if len(keyframes) > max_frames:
            # 均匀选择最重要的帧
            step = len(keyframes) // max_frames
            keyframes = [keyframes[i] for i in range(0, len(keyframes), step)][:max_frames]
            print(f"Limited keyframes to {max_frames} most important ones")
        
        print(f"Scene-based keyframes: {keyframes} (total: {len(keyframes)})")
        frames = [video_clip.get_frame(i / video_clip.fps) for i in keyframes]
        return frames
        
    except Exception as e:
        print(f"Scene-based keyframe extraction error: {str(e)}")
        # 降级到基础采样
        if total_frames <= 100:
            num_frames = 2
        elif total_frames <= 500:
            num_frames = 4
        else:
            num_frames = 6
        return sample_frames(video_clip, num_frames)

def detect_scene_changes_advanced(video_clip, threshold=0.40, min_scene_length=60):
    """
    高级场景变化检测 - 降低密度，提高质量
    """
    try:
        total_frames = int(video_clip.fps * video_clip.duration)
        changes = []
        
        # 增加采样间隔，降低检测密度
        step = max(1, min(25, total_frames // 100))  # 从15增加到25
        
        prev_frame = None
        last_change = 0
        
        for i in range(0, total_frames, step):
            current_frame = video_clip.get_frame(i / video_clip.fps)
            
            if prev_frame is not None:
                # 计算帧间差异
                diff = np.mean(np.abs(current_frame - prev_frame))
                
                # 提高阈值，增加最小场景长度，减少误检
                if diff > threshold * 255 and (i - last_change) >= min_scene_length:
                    changes.append(i)
                    last_change = i
            
            prev_frame = current_frame
        
        print(f"Detected {len(changes)} scene changes at frames: {changes}")
        return changes
        
    except Exception as e:
        print(f"Advanced scene change detection error: {str(e)}")
        return []

def select_key_frames(video_clip, scene_changes):
    """
    选择更关键的帧 - 基于动作和变化的重要性
    """
    key_frames = []
    total_frames = int(video_clip.fps * video_clip.duration)
    
    # 添加起始帧
    key_frames.append(0)
    
    for change_frame in scene_changes:
        # 在场景变化点附近选择最关键的帧
        start_search = max(0, change_frame - 20)
        end_search = min(total_frames - 1, change_frame + 20)
        
        best_frame = change_frame
        max_importance = 0
        
        # 在变化点前后20帧内寻找最关键的帧
        for i in range(start_search, end_search + 1, 5):  # 每5帧检查一次
            if i >= total_frames:
                break
                
            current_frame = video_clip.get_frame(i / video_clip.fps)
            
            # 计算帧的重要性（基于与前后帧的差异）
            importance = 0
            if i > 0:
                prev_frame = video_clip.get_frame((i - 5) / video_clip.fps)
                importance += np.mean(np.abs(current_frame - prev_frame))
            
            if i < total_frames - 1:
                next_frame = video_clip.get_frame((i + 5) / video_clip.fps)
                importance += np.mean(np.abs(current_frame - next_frame))
            
            # 选择重要性最高的帧
            if importance > max_importance:
                max_importance = importance
                best_frame = i
        
        key_frames.append(best_frame)
    
    # 添加结束帧
    key_frames.append(total_frames - 1)
    
    return sorted(list(set(key_frames)))
