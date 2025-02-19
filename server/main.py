from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import tempfile
from werkzeug.utils import secure_filename
from datetime import datetime, UTC
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from docx import Document
from io import BytesIO
import json
import traceback
import bcrypt
import jwt
from functools import wraps
import mimetypes
import shutil
import cv2
import numpy as np
import io
from PIL import Image
import requests
from base64 import b64decode

os.environ["SB_DISABLE_QUIRKS"] = "disable_jit_profiling,allow_tf32"

from .video_analysis import scene_detection, split_video, speech_recognition, generate_clip_descriptions, generate_script
from .ai_assistant import chat_with_ai
from .toggle_chat import handle_scene_chat

# cloudinary
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

cloudinary.config( 
    cloud_name = "dcb4mee54",
    api_key = "112465673685316",
    api_secret = "zklL8gJi-gyc1JgVYDlhDYSg5_M",
    secure=True
)

# MongoDB atlas
uri = "mongodb+srv://juneyxc:GzJjSY7HzROoZrWZ@haiad.jscuo.mongodb.net/?retryWrites=true&w=majority&appName=haiad"
client = MongoClient(uri, server_api=ServerApi('1'))
db = client['haiad']


# 集合定义
videos_collection = db['videos']        # 存储视频信息
scripts_collection = db['scripts']      # 存储脚本信息
human_scripts_collection = db['human_scripts']  # 人工模式脚本
users_collection = db['users']  # 使用users集合
users_collection.create_index('username', unique=True) # 创建用户名索引确保唯一性
chat_history_collection = db['chat_history']
scene_chat_history_collection = db['scene_chat_history']

app = Flask(__name__, 
    static_folder='../views',
    static_url_path=''
)
CORS(app)

# 配置常量
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'webm'}
MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1GB in bytes
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 添加 JSON 编码器
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# 配置 Flask 使用自定义 JSON 编码器
app.json_encoder = MongoJSONEncoder

# 处理所有非 API 路由
@app.route('/')
@app.route('/login')
@app.route('/register')
def serve_vue_app(path=None):
    return send_file('../views/Login.vue')

# API 路由保持不变
@app.route('/api/...')
def api_routes():
    pass

# 处理静态资源
@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_file('../views/Login.vue')

# 添加token验证装饰器
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'message': '未提供token'}), 401
            
        try:
            # 去掉Bearer前缀
            if token.startswith('Bearer '):
                token = token[7:]
            
            # 验证token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            
            # 获取用户信息
            current_user = users_collection.find_one({'_id': ObjectId(data['user_id'])})
            
            if not current_user:
                raise Exception('用户不存在')
                
            # 将用户信息传递给被装饰的函数
            return f(current_user, *args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'token已过期'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': '无效的token'}), 401
        except Exception as e:
            return jsonify({'message': str(e)}), 401
            
    return decorated

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_thumbnail(current_user, file, video_id):
    try:
        # 从数据库获取视频信息
        video = videos_collection.find_one({'_id': ObjectId(video_id)})
        if not video or 'cloudinary_url' not in video:
            raise Exception('Video URL not found')

        video_url = video['cloudinary_url']
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        temp_video_path = os.path.join(temp_dir, f"temp_video_{video_id}.mp4")
        
        try:
            # 使用 requests 下载视频
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            # 保存视频到临时文件
            with open(temp_video_path, 'wb') as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)

            print(f"视频已下载到临时文件: {temp_video_path}")

            # 验证文件是否存在和可读
            if not os.path.exists(temp_video_path):
                raise Exception(f"临时文件不存在: {temp_video_path}")

            # 使用 OpenCV 读取视频
            cap = cv2.VideoCapture(temp_video_path)
            if not cap.isOpened():
                raise Exception("无法打开视频文件")

            ret, frame = cap.read()
            if not ret:
                raise Exception("无法读取视频帧")

            # 生成缩略图
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb_frame)
            image.thumbnail((320, 180))

            # 将图片转换为字节流
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0)

            # 上传到 Cloudinary
            upload_result = cloudinary.uploader.upload(
                img_byte_arr,
                folder=f"users/{str(current_user['_id'])}/thumbnails",
                public_id=f"thumb_{video_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                resource_type="image"
            )

            cap.release()
            return upload_result['secure_url']

        finally:
            # 清理临时文件和目录
            if os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    except Exception as e:
        print(f"生成缩略图错误: {str(e)}")
        traceback.print_exc()
        return None

# 上传视频
@app.route('/api/upload', methods=['POST'])
@token_required
def upload_video(current_user):
    try:
        if 'video' not in request.files:
            return jsonify({'error': '没有选择视频文件'}), 400
            
        file = request.files['video']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
            
        # 检查文件大小
        file.seek(0, 2)  # 移动到文件末尾
        size = file.tell()  # 获取文件大小
        file.seek(0)  # 重置文件指针
        
        if size > MAX_CONTENT_LENGTH:
            return jsonify({
                'success': False,
                'error': f'File too large. Maximum size is {MAX_CONTENT_LENGTH/(1024*1024)}MB'
            }), 413

        if file and allowed_file(file.filename):
            # 确保文件名不会重复.mp4
            filename = secure_filename(file.filename)
            print(f"开始上传文件: {filename}")  # 添加日志
            
            try:
                # 上传到 Cloudinary
                upload_result = cloudinary.uploader.upload(
                    file,
                    resource_type="video",
                    folder=f"users/{str(current_user['_id'])}/videos",
                    public_id=f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename.rsplit('.', 1)[0]}",  # 移除扩展名
                    overwrite=True,
                    chunk_size=6000000,
                    eager=[
                        {"streaming_profile": "full_hd", "format": "m3u8"}
                    ],
                    eager_async=True
                )

                print(f"Cloudinary 上传结果: {upload_result}")

                if not upload_result or 'secure_url' not in upload_result:
                    raise Exception('Failed to upload to Cloudinary')

                # 创建视频记录
                video_id = videos_collection.insert_one({
                    'user_id': ObjectId(current_user['_id']),
                    'filename': filename,
                    'original_filename': file.filename,
                    'created_at': datetime.now(),
                    'has_script': False,
                    'cloudinary_public_id': upload_result['public_id'],
                    'cloudinary_url': upload_result['secure_url'],
                    'cloudinary_resource_type': 'video'
                }).inserted_id

                # 生成缩略图
                thumbnail_url = generate_thumbnail(current_user, file, str(video_id))
                
                if thumbnail_url:
                    videos_collection.update_one(
                        {'_id': ObjectId(video_id)},
                        {'$set': {'thumbnail_url': thumbnail_url}}
                    )

                return jsonify({
                    'success': True,
                    'video_id': str(video_id),
                    'video_url': upload_result['secure_url'],
                    'thumbnail_url': thumbnail_url or ''
                })

            except Exception as e:
                print(f"上传过程中出错: {str(e)}")
                traceback.print_exc()
                return jsonify({'error': f'上传失败: {str(e)}'}), 500

    except Exception as e:
        print(f"外部错误: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# 获取视频
@app.route('/api/videos/<video_id>', methods=['GET'])
@token_required
def get_video(current_user, video_id):
    try:
        # 从数据库获取视频信息，并验证所有权
        video = videos_collection.find_one({
            '_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        
        if not video:
            return jsonify({'error': '视频不存在或无权访问'}), 404

        if 'cloudinary_url' not in video:
            return jsonify({'error': '视频文件不存在'}), 404
            
        # 返回视频的 Cloudinary URL
        return jsonify({
            'success': True,
            'video_url': video.get('cloudinary_url'),  # 这里应该是 playback_url
            'original_url': video.get('secure_url', ''),  # 保存原始视频 URL
            'thumbnail_url': video.get('thumbnail_url', ''),
            'filename': video.get('original_filename', '')
        })
        
    except Exception as e:
        print(f"获取视频错误: {str(e)}")
        traceback.print_exc()  # 添加详细错误日志
        return jsonify({'error': f'获取视频失败: {str(e)}'}), 500


# 删除视频
@app.route('/api/videos/<video_id>', methods=['DELETE'])
@token_required
def delete_video(current_user, video_id):
    try:
        # 查找视频记录
        video = videos_collection.find_one({
            '_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        
        if not video:
            return jsonify({'success': False, 'error': '视频不存在或无权访问'}), 404
            
        # 从 Cloudinary 删除视频
        if 'cloudinary_public_id' in video:
            try:
                result = cloudinary.uploader.destroy(
                    video['cloudinary_public_id'],
                    resource_type=video.get('cloudinary_resource_type', 'video'),
                    invalidate=True
                )
                print(f"视频删除结果: {result}")
            except Exception as e:
                print(f"删除视频文件失败: {str(e)}")
            
        # 从 Cloudinary 删除缩略图
        if 'thumbnail_url' in video:
            try:
                # 从 URL 提取 public_id
                thumbnail_url = video['thumbnail_url']
                public_id = thumbnail_url.split('/')[-1].split('.')[0]
                result = cloudinary.uploader.destroy(
                    public_id,
                    resource_type='image',
                    invalidate=True
                )
                print(f"缩略图删除结果: {result}")
            except Exception as e:
                print(f"删除缩略图失败: {str(e)}")
            
        # 删除相关的脚本
        try:
            scripts_collection.delete_many({
                'video_id': ObjectId(video_id),
                'user_id': ObjectId(current_user['_id'])
            })
        except Exception as e:
            print(f"删除相关脚本失败: {str(e)}")
            
        # 删除视频记录
        result = videos_collection.delete_one({
            '_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        
        if result.deleted_count > 0:
            return jsonify({
                'success': True,
                'message': '视频及其相关资源删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '删除视频记录失败'
            }), 500
        
    except Exception as e:
        print(f"删除视频时出错: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': f'删除失败: {str(e)}'
        }), 500

# 获取所有上传的视频列表
@app.route('/api/videos', methods=['GET'])
@token_required
def get_videos(current_user):
    try:
        videos = videos_collection.find(
            {'user_id': ObjectId(current_user['_id'])}
        ).sort('created_at', -1)
        
        video_list = [{
            'id': str(video['_id']),
            'filename': video['filename'],
            'original_filename': video['original_filename'],
            'status': video.get('status', 'ready'),
            'has_script': video.get('has_script', False),
            'created_at': video['created_at'].isoformat(),
            'video_url': video.get('cloudinary_url', ''),
            'thumbnail_url': video.get('thumbnail_url', '')
        } for video in videos]
        
        return jsonify({
            'success': True,
            'videos': video_list
        })
        
    except Exception as e:
        print(f"Error in get_videos: {str(e)}")
        return jsonify({'success': False, 'error': f'获取视频列表失败: {str(e)}'}), 500

# 分析视频 & 生成初始脚本
@app.route('/api/generatescript', methods=['POST'])
@token_required
def generate_script_endpoint(current_user):
    user_temp_dir = None
    temp_video_path = None
    try:
        data = request.json
        video_id = data.get('video_id')
        if not video_id:
            return jsonify({'error': 'Video ID not provided'}), 400
        
        # 获取视频信息并验证所有权
        video = videos_collection.find_one({
            '_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        if not video:
            return jsonify({'error': 'Video not found or access denied'}), 404

        # 检查 Cloudinary URL
        if 'cloudinary_url' not in video:
            return jsonify({'error': 'Video URL not found'}), 404
            
        # 创建临时目录
        user_temp_dir = os.path.join(tempfile.gettempdir(), f"user_{str(current_user['_id'])}")
        os.makedirs(user_temp_dir, exist_ok=True)

        # 从 Cloudinary 下载视频到临时文件
        temp_video_path = os.path.join(user_temp_dir, f"temp_video_{video_id}.mp4")
        
        try:
            # 使用 requests 下载视频
            response = requests.get(video['cloudinary_url'], stream=True)
            response.raise_for_status()  # 确保请求成功
            
            with open(temp_video_path, 'wb') as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)

            # 使用临时文件路径进行处理
            scenes = scene_detection(temp_video_path)
            clip_paths = split_video(temp_video_path, scenes, user_temp_dir)
            transcript = speech_recognition(temp_video_path)
            clip_descriptions = generate_clip_descriptions(clip_paths, scenes, num_frames=2)
            added_clip_descriptions = clip_descriptions + f'\n\n ASR:{transcript}'
            script_array = generate_script(added_clip_descriptions)
            
            for scene in script_array:
                scene['_id'] = str(ObjectId())
            
            # 保存到数据库
            script_doc = {
                'user_id': ObjectId(current_user['_id']),
                'video_id': ObjectId(video_id),
                'scenes': script_array,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            scripts_collection.update_one(
                {
                    'video_id': ObjectId(video_id),
                    'user_id': ObjectId(current_user['_id'])
                },
                {'$set': script_doc},
                upsert=True
            )
            
            videos_collection.update_one(
                {'_id': ObjectId(video_id)},
                {'$set': {'has_script': True}}
            )

            return jsonify({
                'success': True,
                'scenes': script_array
            })

        except requests.RequestException as e:
            print(f"Failed to download video: {str(e)}")
            return jsonify({'error': f'Failed to download video: {str(e)}'}), 500
        except Exception as e:
            print(f"Inner processing error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Failed to process video: {str(e)}'}), 500

    except Exception as e:
        print(f"Script generation error: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Failed to generate script: {str(e)}'}), 500

    finally:
        # 清理临时文件和目录
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.unlink(temp_video_path)
            except Exception as e:
                print(f"Failed to delete temp video file: {str(e)}")
                
        if user_temp_dir and os.path.exists(user_temp_dir):
            try:
                shutil.rmtree(user_temp_dir)
            except Exception as e:
                print(f"Failed to clean up temp directory: {str(e)}")

# 下载最新的脚本
@app.route('/api/videos/<video_id>/script/download', methods=['GET'])
@token_required
def download_script(current_user, video_id):
    try:
        # 获取指定视频的脚本，并验证所有权
        script = scripts_collection.find_one({
            'video_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        
        if not script:
            return jsonify({'error': '脚本不存在或无权访问'}), 404

        # 创建word文档
        doc = Document()
        
        # 添加场景内容
        scenes = script.get('scenes', [])
        for scene in scenes:
            # 添加时间范围
            time_range = f"{scene.get('start_time', '')} - {scene.get('end_time', '')}"
            doc.add_paragraph(time_range)     
            # 添加场景描述
            description = scene.get('description', '')
            if description:
                doc.add_paragraph(description)
            # 添加空行分隔场景
            doc.add_paragraph('')
        
        # 保存到内存中
        doc_io = BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)
        
        # 生成文件名：AD script_时间戳
        filename = f'AD_script_{datetime.now().strftime("%Y%m%d_%H%M%S")}.docx'
        
        return send_file(
            doc_io,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"生成Word文档失败: {str(e)}")
        return jsonify({'error': f'生成Word文档失败: {str(e)}'}), 500

# 获取所有场景
@app.route('/api/videos/<video_id>/scenes', methods=['GET'])
@token_required
def get_scenes(current_user, video_id):
    try:
        script = scripts_collection.find_one({
            'video_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        if not script:
            return jsonify({'scenes': []})
            
        scenes = script.get('scenes', [])
        for scene in scenes:
            scene['_id'] = str(scene['_id'])
            
        return jsonify({'scenes': scenes})
    except Exception as e:
        return jsonify({'error': f'获取场景失败: {str(e)}'}), 500

# 添加新场景
@app.route('/api/videos/<video_id>/scenes', methods=['POST'])
@token_required
def add_scene(current_user, video_id):
    try:
        data = request.json
        position = data.get('position', 'end')
        index = data.get('index', None)
        
        new_scene = {
            '_id': ObjectId(),
            'scene_number': data.get('scene_number', ''),
            'start_time': data.get('start_time', '00:00:00.000'),
            'end_time': data.get('end_time', '00:00:00.000'),
            'description': data.get('description', '')
        }
        
        update_query = {
            'video_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        }
        
        if position == 'before':
            update_operation = {
                '$push': {
                    'scenes': {
                        '$each': [new_scene],
                        '$position': index
                    }
                }
            }
        elif position == 'after':
            update_operation = {
                '$push': {
                    'scenes': {
                        '$each': [new_scene],
                        '$position': index + 1
                    }
                }
            }
        else:
            update_operation = {
                '$push': {
                    'scenes': new_scene
                }
            }
        
        result = scripts_collection.update_one(update_query, update_operation)
        
        if result.modified_count > 0:
            return jsonify({
                'success': True,
                'scene': {**new_scene, '_id': str(new_scene['_id'])}
            })
        return jsonify({'error': '添加场景失败或无权访问'}), 500
        
    except Exception as e:
        print(f"添加场景时出错: {str(e)}")
        return jsonify({'error': f'添加场景失败: {str(e)}'}), 500

# 获取和更新指定场景
@app.route('/api/videos/<video_id>/scenes/<scene_id>', methods=['PUT'])
@token_required
def handle_scene(current_user, video_id, scene_id):
    try:
        data = request.json
            
        # 首先获取完整的脚本文档
        script = scripts_collection.find_one({
            'video_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
            
        if not script:
            print("未找到对应的脚本")
            return jsonify({'error': '未找到对应的脚本'}), 404
            
        # 找到需要更新的场景在数组中的索引
        scene_index = None
        for i, scene in enumerate(script['scenes']):
            if str(scene['_id']) == scene_id:
                scene_index = i
                break
            
        if scene_index is None:
            print("未找到对应的场景")
            return jsonify({'error': '未找到对应的场景'}), 404
            
        # 构建更新操作
        update_query = {
            'video_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        }
            
        # 使用数组索引直接更新指定场景
        update_operation = {
            '$set': {
                f'scenes.{scene_index}.scene_number': data.get('scene_number', ''),
                f'scenes.{scene_index}.start_time': data.get('start_time', '00:00:00.000'),
                f'scenes.{scene_index}.end_time': data.get('end_time', '00:00:00.000'),
                f'scenes.{scene_index}.description': data.get('description', ''),
                'updated_at': datetime.now(UTC)
            }
        }
            
        result = scripts_collection.update_one(update_query, update_operation)

        if result.matched_count == 0:
            return jsonify({'error': '更新失败，未找到匹配文档'}), 404
                
        if result.modified_count > 0:
            return jsonify({
                'success': True,
                'message': '场景更新成功'
            })
                
        return jsonify({
            'success': False,
            'message': '场景未发生变化'
        })
            
    except Exception as e:
        print(f"更新场景时出错: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'更新场景失败: {str(e)}'
        }), 500

# 删除指定场景
@app.route('/api/videos/<video_id>/scenes/<scene_id>', methods=['DELETE'])
@token_required
def delete_scene(current_user, video_id, scene_id):
    try:
        # 验证视频所有权
        video = videos_collection.find_one({
            '_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        
        if not video:
            return jsonify({'error': 'Video not found or access denied'}), 404

        # 获取当前脚本
        script = scripts_collection.find_one({
            'video_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })

        if not script:
            return jsonify({'error': 'Script not found'}), 404

        # 从场景数组中移除指定场景
        updated_scenes = [scene for scene in script['scenes'] 
                         if str(scene.get('_id', '')) != scene_id]

        # 如果场景数量没有变化，说明没有找到要删除的场景
        if len(updated_scenes) == len(script['scenes']):
            return jsonify({'error': 'Scene not found'}), 404

        # 更新数据库
        result = scripts_collection.update_one(
            {
                'video_id': ObjectId(video_id),
                'user_id': ObjectId(current_user['_id'])
            },
            {
                '$set': {
                    'scenes': updated_scenes,
                    'updated_at': datetime.now()
                }
            }
        )

        if result.modified_count == 0:
            return jsonify({'error': 'Failed to update script'}), 500

        return jsonify({
            'success': True,
            'message': 'Scene deleted successfully'
        })

    except Exception as e:
        print(f"Delete scene error: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Failed to delete scene: {str(e)}'}), 500

# 保存脚本
@app.route('/api/videos/<video_id>/script', methods=['POST'])
@token_required
def save_script(current_user, video_id):
    try:
        data = request.json
        scenes = data.get('scenes', [])
        
        # 获取现有脚本
        script = scripts_collection.find_one({
            'video_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        
        if not script:
            # 如果脚本不存在，创建新的脚本文档
            script_doc = {
                'user_id': ObjectId(current_user['_id']),
                'video_id': ObjectId(video_id),
                'scenes': scenes,
                'content': '',  # 可以根据需要从scenes生成content
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # 创建用户脚本目录
            user_script_dir = f"storage/users/user_{str(current_user['_id'])}/scripts"
            os.makedirs(user_script_dir, exist_ok=True)
            
            # 生成脚本文件名和路径
            script_filename = f"script_{video_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            script_path = os.path.join(user_script_dir, script_filename)
            
            # 保存脚本到文件
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write('')  # 可以根据需要写入内容
                
            script_doc['file_path'] = script_path
            
            result = scripts_collection.insert_one(script_doc)
            success = bool(result.inserted_id)
        else:
            # 更新现有脚本
            update_data = {
                'scenes': scenes,
                'updated_at': datetime.now()
            }
            
            result = scripts_collection.update_one(
                {
                    'video_id': ObjectId(video_id),
                    'user_id': ObjectId(current_user['_id'])
                },
                {'$set': update_data}
            )
            success = result.modified_count > 0
        
        if success:
            return jsonify({'success': True})
        return jsonify({'error': '保存脚本失败或无权访问'}), 500
        
    except Exception as e:
        print(f"保存脚本时出错: {str(e)}")
        return jsonify({'error': f'保存脚本失败: {str(e)}'}), 500

# 获取初始脚本
@app.route('/api/initial-script', methods=['GET'])
@token_required
def get_initial_script(current_user):
    try:
        # 获取用户最新的脚本记录
        script = scripts_collection.find_one(
            {'user_id': ObjectId(current_user['_id'])},
            {'content': 1, '_id': 0},
            sort=[('created_at', -1)]
        )
        
        if not script:
            return jsonify({
                'success': True,
                'script': None
            })
            
        return jsonify({
            'success': True,
            'script': script.get('content')
        })
        
    except Exception as e:
        print(f"获取初始脚本错误: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'获取初始脚本失败: {str(e)}'
        }), 500

# register
@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()  # 使用 get_json() 而不是 json 属性
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400
        
        # 验证必要字段
        if not all(key in data for key in ['username', 'password']):
            return jsonify({'error': '缺少必要字段'}), 400
            
        username = data['username'].strip()  # 去除空白字符
        password = data['password']
        
        # 验证用户名和密码的有效性
        if not username or len(username) < 3:
            return jsonify({'error': '用户名至少需要3个字符'}), 400
            
        if not password or len(password) < 6:
            return jsonify({'error': '密码至少需要6个字符'}), 400
            
        # 检查用户名是否已存在
        if users_collection.find_one({'username': username}):
            return jsonify({'error': '用户名已存在'}), 400
            
        # 对密码进行加密
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # 创建用户文档
        user = {
            'username': username,
            'password': hashed_password,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        # 插入用户数据
        result = users_collection.insert_one(user)
        
        # 生成token
        token = jwt.encode({
            'user_id': str(result.inserted_id),
            'exp': datetime.now().timestamp() + 24*60*60  # 24小时过期
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'token': token,
            'user': {
                'id': str(result.inserted_id),
                'username': username
            }
        })
        
    except Exception as e:
        print(f"注册错误: {str(e)}")
        traceback.print_exc()  # 添加详细的错误追踪
        return jsonify({'error': f'注册失败: {str(e)}'}), 500

# login
@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not all(key in data for key in ['username', 'password']):
            return jsonify({'error': '缺少必要字段'}), 400
            
        username = data['username']
        password = data['password']
        
        # 查找用户
        user = users_collection.find_one({'username': username})
        if not user:
            return jsonify({'error': '用户名或密码错误'}), 401
            
        # 验证密码
        stored_password = user['password']
        if isinstance(stored_password, bytes):
            stored_password = stored_password.decode('utf-8')
            
        if not bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
            return jsonify({'error': '用户名或密码错误'}), 401
            
        # 生成token
        token = jwt.encode({
            'user_id': str(user['_id']),
            'exp': datetime.now().timestamp() + 24*60*60  # 24小时过期
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'token': token,
            'user': {
                'id': str(user['_id']),
                'username': user['username']
            }
        })
        
    except Exception as e:
        print(f"登录错误: {str(e)}")
        return jsonify({'error': f'登录失败: {str(e)}'}), 500

# 保存人工编辑的脚本
@app.route('/api/videos/<video_id>/human-script', methods=['POST'])
@token_required
def save_human_script(current_user, video_id):
    try:
        data = request.json
        script_content = data.get('script', '')
        
        # 获取现有脚本或创建新的
        script = human_scripts_collection.find_one({
            'video_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        
        if not script:
            # 创建新脚本
            script_doc = {
                'user_id': ObjectId(current_user['_id']),
                'video_id': ObjectId(video_id),
                'content': script_content,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            result = human_scripts_collection.insert_one(script_doc)
            success = bool(result.inserted_id)
        else:
            # 更新现有脚本
            update_data = {
                'content': script_content,
                'updated_at': datetime.now()
            }
            
            result = human_scripts_collection.update_one(
                {
                    'video_id': ObjectId(video_id),
                    'user_id': ObjectId(current_user['_id'])
                },
                {'$set': update_data}
            )
            success = result.modified_count > 0
        
        if success:
            return jsonify({'success': True})
        return jsonify({'error': '保存脚本失败'}), 500
        
    except Exception as e:
        print(f"保存脚本时出错: {str(e)}")
        return jsonify({'error': f'保存脚本失败: {str(e)}'}), 500

# 下载人工编辑的脚本
@app.route('/api/videos/<video_id>/human-script/download', methods=['GET'])
@token_required
def download_human_script(current_user, video_id):
    try:
        # 从人工脚本集合中获取脚本
        script = human_scripts_collection.find_one({
            'video_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        
        if not script:
            return jsonify({'error': '脚本不存在'}), 404

        # 创建word文档
        doc = Document()
        
        # 添加标题
        doc.add_heading('广告脚本 - 人工编辑版本', 0)
        
        # 添加创建时间
        doc.add_paragraph(f'创建时间: {script["created_at"].strftime("%Y-%m-%d %H:%M:%S")}')
        doc.add_paragraph(f'最后更新: {script["updated_at"].strftime("%Y-%m-%d %H:%M:%S")}')
        
        # 添加分隔线
        doc.add_paragraph('=' * 50)
        
        # 添加脚本内容
        doc.add_paragraph(script.get('content', ''))
        
        # 保存到内存中
        memory_file = BytesIO()
        doc.save(memory_file)
        memory_file.seek(0)
        
        return send_file(
            memory_file,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=f'AD_script_{datetime.now().strftime("%Y%m%d_%H%M%S")}.docx'
        )      
    except Exception as e:
        print(f"下载脚本时出错: {str(e)}")
        return jsonify({'error': f'下载脚本失败: {str(e)}'}), 500

# 获取人工编辑的脚本
@app.route('/api/videos/<video_id>/human-script', methods=['GET'])
@token_required
def get_human_script(current_user, video_id):
    try:
        script = human_scripts_collection.find_one({
            'video_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        
        if script:
            return jsonify({
                'success': True,
                'content': script.get('content', ''),
                'created_at': script['created_at'].isoformat(),
                'updated_at': script['updated_at'].isoformat()
            })
        else:
            return jsonify({
                'success': True,
                'content': '',
                'created_at': None,
                'updated_at': None
            })
            
    except Exception as e:
        print(f"获取脚本时出错: {str(e)}")
        return jsonify({'error': f'获取脚本失败: {str(e)}'}), 500

@app.route('/api/chat', methods=['POST'])
@token_required
def chat(current_user):
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        image_data = data.get('image')  # Base64 图片数据

        if not message and not image_data:
            return jsonify({
                'success': False,
                'error': 'Message or image is required'
            }), 400

        # 处理图片上传
        image_url = None
        if image_data:
            try:
                # 从 Base64 中提取实际的图片数据
                image_data = image_data.split(',')[1] if ',' in image_data else image_data
                image_bytes = b64decode(image_data)
                
                # 上传到 Cloudinary
                upload_result = cloudinary.uploader.upload(
                    io.BytesIO(image_bytes),
                    folder=f"users/{str(current_user['_id'])}/chat_images",
                    public_id=f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_chat_image",
                    resource_type="auto",
                    overwrite=True
                )
                image_url = upload_result['secure_url']
                print(f"Image uploaded to: {image_url}")
                
            except Exception as e:
                print(f"Error uploading image: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': f'Image upload failed: {str(e)}'
                }), 500

        # 保持原有的消息处理逻辑...
        history_messages = []
        message_count = 0
        MAX_MESSAGES = 10

        chat_history = db.chat_history.find({
            'user_id': ObjectId(current_user['_id'])
        }).sort('created_at', -1).limit(MAX_MESSAGES)

        for chat in chat_history:
            for msg in reversed(chat.get('messages', [])):
                if message_count >= MAX_MESSAGES:
                    break
                    
                content = msg.get('content', '')
                if isinstance(content, list):
                    content = next((item.get('text', '') for item in content if item.get('type') == 'text'), '')

                history_messages.append({
                    'role': msg.get('role', 'user'),
                    'content': content
                })
                message_count += 1

        # 调用 AI 助手，传入有限的历史记录
        try:
            result = chat_with_ai(message, image_url, history_messages)
            
            if not result.get('success'):
                print(f"AI assistant error: {result.get('error')}")
                return jsonify({'error': 'Failed to get AI response'}), 500

            # 保存新对话到数据库
            chat_entry = {
                'user_id': ObjectId(current_user['_id']),
                'messages': [
                    {
                        'role': 'user',
                        'content': message,
                        'image': image_url,
                        'timestamp': datetime.now()
                    },
                    {
                        'role': 'assistant',
                        'content': result['response'],
                        'timestamp': datetime.now()
                    }
                ],
                'created_at': datetime.now()
            }
            
            try:
                chat_history_collection.insert_one(chat_entry)
            except Exception as save_error:
                print(f"Failed to save chat history: {str(save_error)}")
                # 即使保存失败也返回响应
                return jsonify({
                    'success': True,
                    'response': result['response']
                })

            return jsonify({
                'success': True,
                'response': result['response']
            })
            
        except Exception as ai_error:
            print(f"AI processing error: {str(ai_error)}")
            return jsonify({'error': f'AI processing failed: {str(ai_error)}'}), 500

    except Exception as e:
        print(f"General chat endpoint error: {str(e)}")
        return jsonify({'error': f'Failed to process chat: {str(e)}'}), 500

# 添加获取聊天历史的端点
@app.route('/api/chat/history', methods=['GET'])
@token_required
def get_chat_history(current_user):
    try:
        # 获取用户的聊天历史
        history = list(db.chat_history.find(
            {'user_id': ObjectId(current_user['_id'])}
        ).sort('created_at', -1))  # 按时间倒序排列
        
        # 处理 ObjectId 和时间戳
        for chat in history:
            # 转换所有 ObjectId 字段为字符串
            chat['_id'] = str(chat['_id'])
            chat['user_id'] = str(chat['user_id'])
            if 'video_id' in chat:
                chat['video_id'] = str(chat['video_id'])
            if 'scene_id' in chat:
                chat['scene_id'] = str(chat['scene_id'])
            
            # 转换时间戳
            if 'created_at' in chat:
                chat['created_at'] = chat['created_at'].isoformat()
            
            # 处理消息中的时间戳
            for message in chat.get('messages', []):
                if 'timestamp' in message:
                    message['timestamp'] = message['timestamp'].isoformat()
                
                # 确保消息内容是可序列化的
                if isinstance(message.get('content'), list):
                    for item in message['content']:
                        if '_id' in item:
                            item['_id'] = str(item['_id'])
        
        print("Processed chat history:", history)  # 添加调试日志
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        print(f"Get chat history error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to get chat history: {str(e)}'
        }), 500

@app.route('/api/ai/scene/chat', methods=['POST'])
@token_required
def scene_ai_chat(current_user):
    try:
        data = request.get_json()
        print("Received request data:", data)
        
        # 验证必要的参数
        if not all([data.get('video_id'), data.get('scene_id'), data.get('current_text'), data.get('user_message')]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
            
        try:
            # 查找现有的聊天历史
            chat_history = db.chat_history.find_one({
                'user_id': ObjectId(current_user['_id']),
                'video_id': ObjectId(data.get('video_id')),
                'scene_id': ObjectId(data.get('scene_id'))
            })
            
            # 获取历史消息
            chat_histories = chat_history.get('messages', []) if chat_history is not None else []
            
            # 调用 OpenAI 处理函数
            result = handle_scene_chat(
                current_text=data.get('current_text'),
                user_message=data.get('user_message'),
                chat_histories=chat_histories
            )
            
            if result['success']:
                # 准备新的消息
                new_messages = [
                    {
                        'role': 'user',
                        'content': data.get('user_message'),
                        'timestamp': datetime.now(UTC)
                    },
                    {
                        'role': 'assistant',
                        'content': result['message'],
                        'timestamp': datetime.now(UTC)
                    }
                ]
                
                if chat_history is not None:
                    # 更新现有对话
                    db.scene_chat_history.update_one(
                        {'_id': chat_history['_id']},
                        {
                            '$push': {
                                'messages': {
                                    '$each': new_messages
                                }
                            }
                        }
                    )
                else:
                    # 创建新对话
                    chat_entry = {
                        'user_id': ObjectId(current_user['_id']),
                        'video_id': ObjectId(data.get('video_id')),
                        'scene_id': ObjectId(data.get('scene_id')),
                        'messages': new_messages,
                        'created_at': datetime.now(UTC)
                    }
                    db.scene_chat_history.insert_one(chat_entry)
            
            return jsonify(result)
            
        except Exception as e:
            print(f"Database or processing error: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Database or processing error: {str(e)}'
            }), 500

    except Exception as e:
        print(f"Request parsing error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Request parsing error: {str(e)}'
        }), 500

@app.route('/api/ai/scene/chat/history', methods=['GET'])
@token_required
def get_scene_chat_history(current_user):
    try:
        # 获取请求参数
        video_id = request.args.get('video_id')
        scene_id = request.args.get('scene_id')
        
        # 验证必要的参数
        if not all([video_id, scene_id]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
            
        try:
            # 查找聊天历史
            chat_history = db.scene_chat_history.find_one({
                'user_id': ObjectId(current_user['_id']),
                'video_id': ObjectId(video_id),
                'scene_id': ObjectId(scene_id)
            })
            
            if chat_history:
                # 转换 ObjectId 为字符串
                chat_history['_id'] = str(chat_history['_id'])
                chat_history['user_id'] = str(chat_history['user_id'])
                chat_history['video_id'] = str(chat_history['video_id'])
                chat_history['scene_id'] = str(chat_history['scene_id'])
                
                # 转换消息中的时间戳
                for message in chat_history['messages']:
                    if 'timestamp' in message:
                        message['timestamp'] = message['timestamp'].isoformat()
                
                # 转换创建时间
                if 'created_at' in chat_history:
                    chat_history['created_at'] = chat_history['created_at'].isoformat()
                
                return jsonify({
                    'success': True,
                    'history': chat_history
                })
            else:
                return jsonify({
                    'success': True,
                    'history': None
                })
            
        except Exception as e:
            print(f"Database error: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Database error: {str(e)}'
            }), 500

    except Exception as e:
        print(f"Request parsing error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Request parsing error: {str(e)}'
        }), 500

# if __name__ == '__main__':
#     port = int(os.environ.get('PORT', 5002))
#     app.run(host='0.0.0.0', port=port, debug=True)
    