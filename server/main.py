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
import re
import boto3
from botocore.exceptions import ClientError
import hashlib
from datetime import datetime, timezone

os.environ["SB_DISABLE_QUIRKS"] = "disable_jit_profiling,allow_tf32"
from .video_analysis import generate_clip_description, split_video_segment, generate_script_2, generate_script_with_instruction

# =====================================

# Cloudflare R2 配置
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID', "86e5075db5108227c5f1cf3a232e2b39")
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY', "812028cb0ba05a91212e6736cc9d9320a5bd55cf05450bd32cfa57df30a8c474")
R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID', "6290a475a5f7f7788693c04d408474d5")
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME', "haiad-videos")
R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
R2_PUBLIC_URL = os.environ.get('R2_PUBLIC_URL', "https://haiad.app")

# 本地缓存配置
CACHE_DIR = os.environ.get('CACHE_DIR', '/tmp/video_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cached_video_path(video_url):
    """
    获取缓存的视频文件路径，如果不存在则下载
    """
    # 使用URL的hash作为缓存文件名
    url_hash = hashlib.md5(video_url.encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{url_hash}.mp4")
    
    # 如果缓存文件存在且大小大于0，直接返回
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        print(f"使用缓存文件: {cache_path}")
        return cache_path
    
    # 否则下载文件到缓存
    print(f"下载视频到缓存: {video_url}")
    try:
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        
        with open(cache_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"视频已缓存到: {cache_path}")
        return cache_path
        
    except Exception as e:
        print(f"下载视频失败: {str(e)}")
        # 如果缓存文件存在但下载失败，删除损坏的缓存文件
        if os.path.exists(cache_path):
            os.remove(cache_path)
        raise e

# 初始化R2客户端
def get_r2_client():
    """获取R2客户端"""
    session = boto3.session.Session()
    return session.client(
        service_name='s3',
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        endpoint_url=R2_ENDPOINT_URL
    )

# R2 上传函数
def upload_to_r2(file, storage_path):
    """上传文件到 Cloudflare R2"""
    try:
        s3_client = get_r2_client()
        
        # 读取文件内容
        file.seek(0)
        file_content = file.read()
        
        # 上传到 R2
        response = s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=storage_path,
            Body=file_content,
            ContentType='application/octet-stream'
        )
        
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            # 返回公共访问URL
            public_url = f"{R2_PUBLIC_URL}/{storage_path}"
            return {
                'success': True,
                'cdn_url': public_url,
                'storage_path': storage_path
            }
        else:
            print(f"R2 上传失败: {response}")
            return {'success': False, 'error': 'Upload failed'}
            
    except ClientError as e:
        print(f"R2 上传错误: {str(e)}")
        return {'success': False, 'error': str(e)}
    except Exception as e:
        print(f"R2 上传错误: {str(e)}")
        return {'success': False, 'error': str(e)}

def delete_from_r2(storage_path):
    """从 R2 删除文件"""
    try:
        s3_client = get_r2_client()
        
        response = s3_client.delete_object(
            Bucket=R2_BUCKET_NAME,
            Key=storage_path
        )
        
        if response['ResponseMetadata']['HTTPStatusCode'] == 204:
            return True
        else:
            print(f"R2 删除失败: {response}")
            return False
            
    except ClientError as e:
        print(f"R2 删除错误: {str(e)}")
        return False
    except Exception as e:
        print(f"R2 删除错误: {str(e)}")
        return False

# MongoDB atlas
uri = "mongodb+srv://juneyxc:GzJjSY7HzROoZrWZ@haiad.jscuo.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(uri, server_api=ServerApi('1'))
db = client['haiad']

# 集合定义
videos_collection = db['videos']        # 存储视频信息
scripts_collection = db['scripts']      # 存储脚本信息
users_collection = db['users']  # 使用users集合
users_collection.create_index('username', unique=True) # 创建用户名索引确保唯一性
chat_logging_collection = db['chat_logging']  # 存储LOG日志

app = Flask(__name__)
CORS(app, supports_credentials=True)

@app.route("/")
def home():
    return {"message": "Flask is running on Render!"}

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
        if not video or 'r2_url' not in video:
            raise Exception('Video URL not found')

        video_url = video['r2_url']
        
        # 使用缓存系统获取视频文件
        cached_video_path = get_cached_video_path(video_url)
        
        print(f"使用缓存视频生成缩略图: {cached_video_path}")

        # 验证文件是否存在和可读
        if not os.path.exists(cached_video_path):
            raise Exception(f"缓存文件不存在: {cached_video_path}")

        # 使用 OpenCV 读取视频
        cap = cv2.VideoCapture(cached_video_path)
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

        # 上传缩略图到 R2
        timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        thumbnail_path = f"users/{str(current_user['_id'])}/thumbnails/thumb_{video_id}_{timestamp}.jpg"
        
        # 上传缩略图到R2
        s3_client = get_r2_client()
        response = s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=thumbnail_path,
            Body=img_byte_arr.getvalue(),
            ContentType='image/jpeg'
        )
        
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            thumbnail_url = f"{R2_PUBLIC_URL}/{thumbnail_path}"
            cap.release()
            return thumbnail_url
        else:
            print(f"缩略图上传失败: {response}")
            cap.release()
            return None

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
            
        # 获取视频背景信息
        video_context = request.form.get('video_context', '')
        
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
            print(f"视频背景信息: {video_context}")  # 新增：打印背景信息
            
            try:
                # 生成存储路径
                timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
                storage_path = f"users/{str(current_user['_id'])}/videos/{timestamp}_{filename}"
                
                # 上传到 R2
                upload_result = upload_to_r2(file, storage_path)

                print(f"R2 上传结果: {upload_result}")

                if not upload_result or not upload_result.get('success'):
                    raise Exception(f'Failed to upload to R2: {upload_result.get("error", "Unknown error")}')

                # 创建视频记录
                video_id = videos_collection.insert_one({
                    'user_id': ObjectId(current_user['_id']),
                    'filename': filename,
                    'original_filename': file.filename,
                    'created_at': datetime.now(UTC),
                    'has_script': False,
                    'r2_storage_path': upload_result['storage_path'],
                    'r2_url': upload_result['cdn_url'],
                    'video_context': video_context  # 新增：保存视频背景信息
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
                    'video_url': upload_result['cdn_url'],
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

        if 'r2_url' not in video:
            return jsonify({'error': '视频文件不存在'}), 404
            
        # 返回视频的 R2 URL
        return jsonify({
            'success': True,
            'video_url': video.get('r2_url'),
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
            
        # 从 R2 删除视频
        if 'r2_storage_path' in video:
            try:
                result = delete_from_r2(video['r2_storage_path'])
                print(f"视频删除结果: {result}")
            except Exception as e:
                print(f"删除视频文件失败: {str(e)}")
            
        # 从 R2 删除缩略图
        if 'thumbnail_url' in video:
            try:
                # 从公共URL提取存储路径
                thumbnail_url = video['thumbnail_url']
                # 从公共URL中提取存储路径
                # 例如: https://your-custom-domain.com/users/xxx/thumbnails/thumb_xxx.jpg
                storage_path = thumbnail_url.replace(f"{R2_PUBLIC_URL}/", '')
                print(f"正在删除缩略图，storage_path: {storage_path}")
                
                result = delete_from_r2(storage_path)
                print(f"缩略图删除结果: {result}")
            except Exception as e:
                print(f"删除缩略图失败: {str(e)}")
                print(f"缩略图 URL: {thumbnail_url}")
                traceback.print_exc()
            
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
            'video_url': video.get('r2_url', ''),
            'thumbnail_url': video.get('thumbnail_url', '')
        } for video in videos]
        
        return jsonify({
            'success': True,
            'videos': video_list
        })
        
    except Exception as e:
        print(f"Error in get_videos: {str(e)}")
        return jsonify({'success': False, 'error': f'获取视频列表失败: {str(e)}'}), 500

# 生成初始6个空场景
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
        
        try:

            script_array = []
            # time = '00:00:00.000'
            for i in range(6):
                dic = {'_id': i, 'start_time': '00:00:00.000', 'end_time': '00:00:00.000', 'description': ''}
                script_array.append(dic)
            for scene in script_array:
                scene['_id'] = str(ObjectId())
            # script_array=[{'scene_number': '1', 'start_time': '00:00:00.000', 'end_time': '00:00:00.000', 'description': ''}]
            
            # 保存到数据库
            script_doc = {
                'user_id': ObjectId(current_user['_id']),
                'video_id': ObjectId(video_id),
                'scenes': script_array,
                'created_at': datetime.now(UTC),
                'updated_at': datetime.now(UTC)
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
        filename = f'AD_script_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.docx'
        
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
                    'updated_at': datetime.now(UTC)
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
                'created_at': datetime.now(UTC),
                'updated_at': datetime.now(UTC)
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
                'updated_at': datetime.now(UTC)
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
            'created_at': datetime.now(UTC),
            'updated_at': datetime.now(UTC)
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

@app.route('/api/ai/scene/description', methods=['POST'])
@token_required
def generate_scene_description(current_user):
    user_temp_dir = None
    temp_video_path = None
    try:
        # 获取参数
        data = request.get_json()
        video_id = data.get('video_id')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        creativity = data.get('creativity')
        video_context = data.get('video_context', '')  # 新增：获取视频背景信息
        try:
            creativity = float(creativity)
        except Exception:
            print(f"creativity类型转换失败，原始值: {creativity}, 类型: {type(creativity)}，已重置为5.0")
            creativity = 5.0
        print(f"creativity的值: {creativity}, 类型: {type(creativity)}")
        
        print("接收到的参数:", {   
        'video_id': data.get('video_id'),
        'start_time': data.get('start_time'),
        'end_time': data.get('end_time'),
        'creativity': data.get('creativity'),
        'video_context': data.get('video_context')})

        if not video_id:
            return jsonify({'error': 'Video ID not provided'}), 400
        
        # 时间格式验证
        if not re.match(r'^\d{2}:\d{2}:\d{2}\.\d{3}$', data['start_time']) or \
            not re.match(r'^\d{2}:\d{2}:\d{2}\.\d{3}$', data['end_time']):
                return jsonify({'error': '时间格式应为 HH:MM:SS.sss'}), 400

        # 获取视频信息并验证所有权
        video = videos_collection.find_one({
            '_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        if not video:
            return jsonify({'error': 'Video not found or access denied'}), 404

        # 检查 R2 URL
        if 'r2_url' not in video:
            return jsonify({'error': 'Video URL not found'}), 404
            
        # 获取视频背景信息
        video_context = video.get('video_context', '')

        # 创建临时目录
        user_temp_dir = os.path.join(tempfile.gettempdir(), f"user_{str(current_user['_id'])}")
        os.makedirs(user_temp_dir, exist_ok=True)

        # 从 R2 下载视频到临时文件
        temp_video_path = os.path.join(user_temp_dir, f"temp_video_{video_id}.mp4")
        
        try:
            cached_video_path = get_cached_video_path(video['r2_url'])
            temp_video_path = cached_video_path  # 直接使用缓存文件

            # 使用临时文件路径进行处理
            # scene = scene_detection(temp_video_path)
            clip_path = split_video_segment(temp_video_path, start_time, end_time, user_temp_dir)
            
            # 检查视频切片是否成功
            if not clip_path:
                return jsonify({'error': 'Failed to split video segment'}), 500

            # num_frames = frame_number(start_time, end_time)
            # print("num_frames是",num_frames)
            # transcript = speech_recognition(clip_path)
            clip_description = generate_clip_description(clip_path, creativity, video_context=video_context)
            # if transcript:
            #     clip_descriptions = clip_descriptions + f'\n\n ASR:{transcript}'
            script_array = generate_script_2(clip_description)
            

            print("切片路径开始===")
            print("切片路径是：",clip_path)
            print("切片路径结束===")


            print("音频描述开始======")
            print("音频描述是",clip_description)
            print("音频描述结束======")


            # description = script_array
            print("开始======")
            print("description是",script_array)
            print("description的类型是",type(script_array))
            print("======结束")

            combined_descriptions = []
            for script in script_array:
                combined_descriptions.append(script['description'])

            # combined_descriptions = '<br>'.join([script['description'] for script in script_array])
            print(combined_descriptions)
            
            # +++ log日志记录到MongoDB +++
            try:
                # 获取标签数据
                tags = data.get('tags')
                tag_str = ",".join(tags) if tags and isinstance(tags, list) else None
                
                # 创建日志文档
                log_entry = {
                    #'user_id': data.get('user_id'),
                    'user_id': ObjectId(current_user['_id']),
                    'videos_id': data.get('video_id'),
                    'descriptions': combined_descriptions,
                    'description_type': 1,  # 描述类型为1
                    'time': datetime.now(UTC),
                    'temperature': creativity,
                    'tag': None,
                    'user_input': None
                }
                
                # 插入到MongoDB
                chat_logging_collection.insert_one(log_entry)
                
            except Exception as e:
                print(f"Error saving log to MongoDB: {str(e)}")


            # for scene in script_array:
            #     scene['_id'] = str(ObjectId())
            
            # # 保存到数据库
            # script_doc = {
            #     'user_id': ObjectId(current_user['_id']),
            #     'video_id': ObjectId(video_id),
            #     'scenes': script_array,
            #     'created_at': datetime.now(),
            #     'updated_at': datetime.now()
            # }
            
            # scripts_collection.update_one(
            #     {
            #         'video_id': ObjectId(video_id),
            #         'user_id': ObjectId(current_user['_id'])
            #     },
            #     {'$set': script_doc},
            #     upsert=True
            # )
            
            # videos_collection.update_one(
            #     {'_id': ObjectId(video_id)},
            #     {'$set': {'has_script': True}}
            # )

            return jsonify({
                'success': True,
                # 'descriptions': combined_descriptions
                'descriptions': [
                    combined_descriptions[0],
                    combined_descriptions[1],
                    combined_descriptions[2],
                    # combined_descriptions[3],
                    # combined_descriptions[4]
                    ]

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
        # 清理临时目录（不删除缓存文件）
        if user_temp_dir and os.path.exists(user_temp_dir):
            try:
                shutil.rmtree(user_temp_dir)
            except Exception as e:
                print(f"Failed to clean up temp directory: {str(e)}")

@app.route('/api/ai/scene/description2', methods=['POST'])
@token_required
def generate_scene_description2(current_user):
    user_temp_dir = None
    temp_video_path = None
    try:
        # 获取参数
        data = request.get_json()      
        video_id = data.get('video_id')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        creativity = data.get('creativity', 5)
        try:
            creativity = float(creativity)
        except Exception:
            print(f"creativity类型转换失败，原始值: {creativity}, 类型: {type(creativity)}，已重置为5.0")
            creativity = 5.0
        print(f"creativity的值: {creativity}, 类型: {type(creativity)}")
        selected_keywords = data.get('selected_keywords', [])  # 用户选择的风格按钮
        additional_instructions = data.get('additional_instructions', '')  # 用户输入内容


        print("接收到的参数:", {   
        'video_id': data.get('video_id'),
        'start_time': data.get('start_time'),
        'end_time': data.get('end_time'),
        'creativity': data.get('creativity'),
        'selected_keywords':data.get('selected_keywords', []),
        'additional_instructions':data.get('additional_instructions', '')
        })

        if not video_id:
            return jsonify({'error': 'Video ID not provided'}), 400
        
        # 时间格式验证
        # if not re.match(r'^\d{2}:\d{2}:\d{2}\.\d{3}$', data['start_time']) or \
        #     not re.match(r'^\d{2}:\d{2}:\d{2}\.\d{3}$', data['end_time']):
        #         return jsonify({'error': '时间格式应为 HH:MM:SS.sss'}), 400

        # 获取视频信息并验证所有权
        video = videos_collection.find_one({
            '_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id'])
        })
        if not video:
            return jsonify({'error': 'Video not found or access denied'}), 404

        # 检查 R2 URL
        if 'r2_url' not in video:
            return jsonify({'error': 'Video URL not found'}), 404
            
        # 获取视频背景信息
        video_context = video.get('video_context', '')

        # 创建临时目录
        user_temp_dir = os.path.join(tempfile.gettempdir(), f"user_{str(current_user['_id'])}")
        os.makedirs(user_temp_dir, exist_ok=True)

        # 使用缓存系统获取视频文件
        try:
            cached_video_path = get_cached_video_path(video['r2_url'])
            temp_video_path = cached_video_path  # 直接使用缓存文件

            # 使用临时文件路径进行处理
            # scene = scene_detection(temp_video_path)
            clip_path = split_video_segment(temp_video_path, start_time, end_time, user_temp_dir)
            
            # 检查视频切片是否成功
            if not clip_path:
                return jsonify({'error': 'Failed to split video segment'}), 500
            
            # num_frames = frame_number(start_time, end_time)
            # print("num_frames是",num_frames)
            # transcript = speech_recognition(clip_path) 
            clip_description = generate_clip_description(clip_path, creativity, video_context=video_context)
            # if transcript:
            #     clip_descriptions = clip_descriptions + f'\n\n ASR:{transcript}'
            script_array = generate_script_with_instruction(clip_description,selected_keywords,additional_instructions)
            
            print("切片路径开始===")
            print("切片路径是：",clip_path)
            print("切片路径结束===")


            print("音频描述开始======")
            print("音频描述是",clip_description)
            print("音频描述结束======")

            # description = script_array
            print("开始======")
            print("description是",script_array)
            print("description的类型是",type(script_array))
            print("======结束")

            combined_descriptions = []
            for script in script_array:
                combined_descriptions.append(script['description'])

            # combined_descriptions = '<br>'.join([script['description'] for script in script_array])
            print(combined_descriptions)
            

            # +++ log记录到MongoDB +++
            try:

                # 创建日志文档
                log_entry = {
                    #'user_id': data.get('user_id'),
                    'user_id': ObjectId(current_user['_id']),
                    'videos_id': data.get('video_id'),
                    'descriptions': combined_descriptions,
                    'description_type': 2,  # 描述类型为2
                    'time': datetime.now(UTC),
                    'temperature': creativity,
                    'tag': selected_keywords,
                    'user_input': additional_instructions
                }
                
                # 插入到MongoDB
                chat_logging_collection.insert_one(log_entry)
                
            except Exception as e:
                print(f"Error saving log to MongoDB: {str(e)}")



            # for scene in script_array:
            #     scene['_id'] = str(ObjectId())
            
            # # 保存到数据库
            # script_doc = {
            #     'user_id': ObjectId(current_user['_id']),
            #     'video_id': ObjectId(video_id),
            #     'scenes': script_array,
            #     'created_at': datetime.now(),
            #     'updated_at': datetime.now()
            # }
            
            # scripts_collection.update_one(
            #     {
            #         'video_id': ObjectId(video_id),
            #         'user_id': ObjectId(current_user['_id'])
            #     },
            #     {'$set': script_doc},
            #     upsert=True
            # )
            
            # videos_collection.update_one(
            #     {'_id': ObjectId(video_id)},
            #     {'$set': {'has_script': True}}
            # )

            return jsonify({
                'success': True,
                # 'descriptions': combined_descriptions
                'descriptions': [
                    combined_descriptions[0],
                    combined_descriptions[1],
                    combined_descriptions[2],
                    # combined_descriptions[3],
                    # combined_descriptions[4]
                    ]

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
        if user_temp_dir and os.path.exists(user_temp_dir):
            try:
                shutil.rmtree(user_temp_dir)
            except Exception as e:
                print(f"Failed to clean up temp directory: {str(e)}")




# if __name__ == '__main__':
#     port = int(os.environ.get('PORT', 5002))
#     app.run(host='0.0.0.0', port=port, debug=True)
