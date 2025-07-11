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
            '-preset', 'veryfast',
            '-crf', '23',
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
def generate_clip_description(clip_path, creativity, num_frames=2, max_retries=100):
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
                    max_tokens=1000,
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
        frames = sample_frames(clip, num_frames)
        images = [Image.fromarray(frame) for frame in frames]
        image_files = [convert_to_base64(image) for image in images]

        content = []
        prompt = (
            "You are an expert in understanding scene transitions based on visual features in a video. "
            "For the given sequence of images per timestamp, identify the scene in the video. "
            "Generate audio description for the each scene."
            "Return the audio description for all scenes in a coherence paragraph and absolutely do not add time ranges and any additionalinformation.\n"
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

        prompt = (
            "You are an expert in writing audio descriptions for videos. "
            "Please generate audio descriptions in 5 distinct writing styles. "

            "The five styles are:\n"
            "1. Concise and Objective – minimal adjectives, factual tone.\n"
            "2. Descriptive and Evocative – uses rich imagery and sensory language.\n"
            "3. Conversational and Informal – casual, friendly tone.\n"
            "4. Interpretive or Emotive – reflects mood, emotion, or intention.\n"
            "5. Child-Friendly and Simplified – simple, playful, age-appropriate vocabulary.\n\n"
            
            "For each style, generate a continuous paragraph describing the scene(s) in the corresponding style. \n"
            "Please return the five audio descriptions as a Python List of dictionaries, where each dictionary contains: \n"
            "{description_number (str), description (str)}\n\n"
            "Please return the Python List of dictionaries as the final output and do not add any additional information. \n\n"
        )

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
            "You are an expert in writing high-quality audio descriptions for video scenes. "
            "Based on the following visual content, please generate audio description in 5 different versions.\n\n"
            "Each version should include coherent, non-overlapping time-based descriptions, where each time segment is described using one concise sentence. "
            "Do not introduce content not found in the visuals, but you may vary tone, word choice, and phrasing for different versions."
            "For each versions, generate a continuous paragraph describing the scene(s) in the user-defined writing style and follow additional user-defined requirements. \n\n"
            "Please return the 5 audio descriptions as a Python List of dictionaries, where each dictionary contains: \n"
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


def frame_number(start_str, end_str):
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
        seconds_tuple = divmod(total_microseconds, 1_000_000)
        seconds = seconds_tuple[0]  # 只取秒数部分
        
        # 根据视频时长确定抽帧数量
        duration = int(seconds)
        if duration <= 10:
            num_frames = 2
        elif duration <= 30:
            num_frames = 4
        elif duration <= 60:
            num_frames = 6
        else:
            num_frames = 10
        # print("num_frames是",num_frames)
        return num_frames
    
    except ValueError as e:
        # print(f"时间格式错误: {str(e)}")
        return 2
