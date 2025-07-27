from moviepy.video.io.VideoFileClip import VideoFileClip
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
        
        frames = []
        for i in frame_indices:
            try:
                # 确保帧索引在有效范围内
                if i < 0 or i >= total_frames:
                    continue
                frame = video_clip.get_frame(i / video_clip.fps)
                frames.append(frame)
            except Exception as e:
                print(f"Error reading frame {i}: {str(e)}")
                continue
        
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
        
        # 修复文件名：将冒号和点号替换为下划线，确保文件名兼容性
        safe_start_time = start_time_str.replace(':', '_').replace('.', '_')
        safe_end_time = end_time_str.replace(':', '_').replace('.', '_')
        clip_path = os.path.join(output_dir, f"clip_{safe_start_time}_{safe_end_time}.mp4")
        
        print(f"生成的文件路径: {clip_path}")
        
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
        # 使用混合帧提取策略
        frames = hybrid_frame_extraction(clip)
        print(f"Dynamic frame calculation: {len(frames)} frames for {clip.duration:.1f}s video")
        images = [Image.fromarray(frame) for frame in frames]
        image_files = [convert_to_base64(image) for image in images]

        content = []
        
        # 基础prompt
        prompt = (
            "You are an expert in understanding scene transitions based on visual features in a video. "
            "Given a sequence of video keyframes with timestamps, identify different scenes in the video. "
            "For each identified scene, provide a pure audio description in one short sentence. "
            "Focus on describing the characters,actions, objects and text in the scenes. Avoid subjective analysis.\n\n"

            "Please return the description for each scene as a Python List of dictionaries, where each dictionary contains: \n"
            "{time_range (str), description (str)}\n\n"
            "Please return the Python List of dictionaries as the final output and do not add any additional information. \n\n"
        )
        
        # 如果有视频背景信息，添加到prompt中
        if video_context:
            prompt += f"Video Context: {video_context}\n\n"

        content.append({"type": "text", "text": prompt})
        for image_file in image_files:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_file}"}
            })

        description = call_with_limit(content, max_retries)
        descriptions.append(description)
        clip.close()
        return "".join(descriptions)  # 返回列表而不是字符串

    except Exception as e:
        print(f"Generate clip description error: {str(e)}")
        # 返回一个有效的字符串格式
        return "Error: Cannot generate scene description."


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
            "Your task is to synthesize all the AD snippets and generate a full and coherent AD of the entire clip, in 3 different writing styles.\n\n"

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
            "Your task is to synthesize all the AD snippets and generate a full and coherent AD of the entire clip.\n\n"

            "You should rewrite them in 3 different versions based on the user-defined style and insructions."
            "For each version, return a well-structured description composed of several short sentences synthesizing all the AD snippets."
            "Do not include any special characters, code formatting, or non-English text.\n\n"

            "Please return the 3 versions of audio descriptions as a Python List of dictionaries, where each dictionary contains: \n"
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


def calculate_dynamic_frames(duration_seconds):
    """
    动态计算抽帧数量 - 每3秒1帧，无差别处理
    """
    duration = int(duration_seconds)
    
    # 基础配置
    max_frames = 60
    

    # 每3秒1帧，无差别处理
    frames = duration // 3
    # 确保短视频有足够的基础帧
    if frames < 2:
        frames = 2
    
    # 确保不超过最大帧数
    return min(frames, max_frames)

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

# def action_based_keyframe_selection(video_clip):
#     """
#     纯动作检测 - 基于动作强度选择关键帧
#     """
#     total_frames = int(video_clip.fps * video_clip.duration)
#     action_scores = []
    
#     # 检查每一帧的动作强度
#     for i in range(0, total_frames, 10):  # 每10帧检查一次
#         if i >= total_frames:
#             break
            
#         try:
#             current_frame = video_clip.get_frame(i / video_clip.fps)
            
#             # 计算与前后帧的差异（动作强度）
#             action_score = 0
#             if i > 0:
#                 prev_frame = video_clip.get_frame((i - 10) / video_clip.fps)
#                 action_score += np.mean(np.abs(current_frame - prev_frame))
            
#             if i < total_frames - 1:
#                 next_frame = video_clip.get_frame((i + 10) / video_clip.fps)
#                 action_score += np.mean(np.abs(current_frame - next_frame))
            
#             action_scores.append((i, action_score))
#         except:
#             continue
    
#     # 选择动作强度最高的帧
#     action_scores.sort(key=lambda x: x[1], reverse=True)
    
#     # 选择前6个最高动作强度的帧
#     keyframes = [0]  # 起始帧
#     for frame_idx, score in action_scores[:6]:
#         keyframes.append(frame_idx)
    
#     keyframes.append(total_frames - 1)  # 结束帧
#     keyframes = sorted(list(set(keyframes)))
    
#     # 转换为实际的帧
#     frames = [video_clip.get_frame(i / video_clip.fps) for i in keyframes]
    
#     print(f"Action-based keyframes: {keyframes} (total: {len(keyframes)})")
#     return frames

def hybrid_frame_extraction(video_clip):
    """
    混合策略：动态帧数 + 动作检测补充
    """
    total_frames = int(video_clip.fps * video_clip.duration)
    video_duration = video_clip.duration
    
    # 1. 基础动态帧数
    base_frames = calculate_dynamic_frames(video_duration)
    
    # 2. 动作检测 - 选择动作强度最高的帧
    action_scores = []
    
    # 预加载帧，避免重复读取
    frame_cache = {}
    
    # 检查每一帧的动作强度 - 提高采样频率
    for i in range(0, total_frames, 5):  # 每5帧检查一次（之前是10）
        if i >= total_frames:
            break
            
        try:
            # 缓存当前帧
            if i not in frame_cache:
                frame_cache[i] = video_clip.get_frame(i / video_clip.fps)
            current_frame = frame_cache[i]
            
            # 计算与前后帧的差异（动作强度）
            action_score = 0
            if i > 0:
                prev_idx = max(0, i - 5)  # 确保不超出范围
                if prev_idx not in frame_cache:
                    try:
                        frame_cache[prev_idx] = video_clip.get_frame(prev_idx / video_clip.fps)
                    except:
                        continue
                prev_frame = frame_cache[prev_idx]
                action_score += np.mean(np.abs(current_frame - prev_frame))
            
            if i < total_frames - 1:
                next_idx = min(total_frames - 1, i + 5)  # 确保不超出范围
                if next_idx not in frame_cache:
                    try:
                        frame_cache[next_idx] = video_clip.get_frame(next_idx / video_clip.fps)
                    except:
                        continue
                next_frame = frame_cache[next_idx]
                action_score += np.mean(np.abs(current_frame - next_frame))
            
            action_scores.append((i, action_score))
        except Exception as e:
            print(f"Error processing frame {i}: {str(e)}")
            continue
    
    # 选择动作强度最高的帧
    action_scores.sort(key=lambda x: x[1], reverse=True)
    
    # 3. 合并策略：基础帧 + 动作帧
    all_frames = []
    added_times = []  # 记录已添加帧的时间
    
    # 先添加基础均匀采样帧
    uniform_frames = sample_frames(video_clip, base_frames)
    all_frames.extend(uniform_frames)
    
    # 计算基础帧的时间点
    for i, frame in enumerate(uniform_frames):
        frame_time = (i * video_duration) / base_frames
        added_times.append(frame_time)
    
    # 再添加动作帧（避免重复）
    action_frames_added = 0
    # 修复逻辑：确保至少有2个动作帧，最多5个
    max_action_frames = max(2, min(5, base_frames // 2)) if base_frames > 1 else 2
    
    for frame_idx, score in action_scores:
        if action_frames_added >= max_action_frames:
            break
            
        # 检查是否与现有帧重复（时间接近）
        frame_time = frame_idx / video_clip.fps
        is_duplicate = False
        
        for added_time in added_times:
            if abs(frame_time - added_time) < 1.0:  # 1秒内认为是重复
                is_duplicate = True
                break
        
        if not is_duplicate:
            try:
                # 确保帧索引在有效范围内
                if frame_idx < 0 or frame_idx >= total_frames:
                    continue
                    
                # 使用缓存的帧
                if frame_idx in frame_cache:
                    frame = frame_cache[frame_idx]
                else:
                    frame = video_clip.get_frame(frame_idx / video_clip.fps)
                all_frames.append(frame)
                added_times.append(frame_time)
                action_frames_added += 1
            except Exception as e:
                print(f"Error reading action frame {frame_idx}: {str(e)}")
                continue
    
    # 按时间顺序重新排列帧
    frame_time_pairs = []
    frame_idx = 0
    
    # 为每个帧计算时间
    for i, frame in enumerate(all_frames):
        if i < len(uniform_frames):
            # 基础帧的时间
            frame_time = (i * video_duration) / base_frames
        else:
            # 动作帧的时间
            action_frame_idx = i - len(uniform_frames)
            if action_frame_idx < len(added_times) - len(uniform_frames):
                frame_time = added_times[len(uniform_frames) + action_frame_idx]
            else:
                frame_time = video_duration  # 默认放在最后
        
        frame_time_pairs.append((frame_time, frame))
    
    # 按时间排序
    frame_time_pairs.sort(key=lambda x: x[0])
    all_frames = [frame for _, frame in frame_time_pairs]
    
    print(f"Hybrid extraction: {base_frames} base + {action_frames_added} action = {len(all_frames)} total frames")
    print(f"Video duration: {video_duration:.1f}s")
    # print(f"number of all frames: {len(all_frames)}")
    
    return all_frames