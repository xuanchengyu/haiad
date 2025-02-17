from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import tempfile
from werkzeug.utils import secure_filename
from datetime import datetime
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import gridfs
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

from .video_analysis import scene_detection, split_video, speech_recognition, generate_clip_descriptions, generate_script
from .ai_assistant import chat_with_ai

# MongoDB 配置
uri = "mongodb+srv://juneyxc:GzJjSY7HzROoZrWZ@haiad.jscuo.mongodb.net/?retryWrites=true&w=majority&appName=haiad"
client = MongoClient(uri, server_api=ServerApi('1'))
db = client['haiad']
fs = gridfs.GridFS(db)  # 用于存储文件

# 集合定义
videos_collection = db['videos']        # 存储视频信息
scripts_collection = db['scripts']      # 存储脚本信息
human_scripts_collection = db['human_scripts']  # 人工模式脚本
users_collection = db['users']  # 使用users集合
users_collection.create_index('username', unique=True) # 创建用户名索引确保唯一性
chat_history_collection = db['chat_history']

app = Flask(__name__)
CORS(app)

# 配置常量
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'webm'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
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

@app.route("/")
def home():
    return {"message": "Flask is running with Gunicorn on Render!"}

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

def generate_thumbnail(video_path, video_id):
    try:
        # 打开视频文件
        cap = cv2.VideoCapture(video_path)
        
        # 读取第一帧
        ret, frame = cap.read()
        if ret:
            # 将 OpenCV 的 BGR 格式转换为 RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 将 numpy array 转换为 PIL Image
            image = Image.fromarray(rgb_frame)
            
            # 调整图片大小（可选）
            image.thumbnail((320, 180))  # 16:9 比例
            
            # 将图片转换为字节流
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_byte_arr = img_byte_arr.getvalue()
            
            # 存储到 GridFS
            thumbnail_id = fs.put(
                img_byte_arr,
                filename=f"{video_id}_thumb.jpg",
                content_type='image/jpeg'
            )
            
            # 更新视频记录中的缩略图ID
            videos_collection.update_one(
                {'_id': ObjectId(video_id)},
                {'$set': {'thumbnail_id': thumbnail_id}}
            )
            
            cap.release()
            return str(thumbnail_id)
            
    except Exception as e:
        print(f"Error generating thumbnail: {str(e)}")
        return None

# 添加获取缩略图的路由
@app.route('/api/thumbnails/<thumbnail_id>')
def get_thumbnail(thumbnail_id):
    try:
        # 从 GridFS 获取缩略图
        file = fs.get(ObjectId(thumbnail_id))
        return send_file(
            io.BytesIO(file.read()),
            mimetype='image/jpeg'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 404

# 上传视频
@app.route('/api/upload', methods=['POST'])
@token_required
def upload_video(current_user):
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'No video file'}), 400
            
        file = request.files['video']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # 将视频文件保存到 GridFS
            file_id = fs.put(
                file,
                filename=filename,
                content_type=file.content_type,
                user_id=ObjectId(current_user['_id'])  # 添加用户ID作为元数据
            )
            
            # 创建视频记录
            video_id = videos_collection.insert_one({
                'user_id': ObjectId(current_user['_id']),
                'filename': filename,
                'original_filename': file.filename,
                'created_at': datetime.now(),
                'has_script': False,
                'file_id': file_id  # 存储 GridFS 文件ID
            }).inserted_id
            
            # 生成并保存缩略图
            # 首先从 GridFS 读取视频文件到临时文件
            video_data = fs.get(file_id)
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                temp_file.write(video_data.read())
                temp_path = temp_file.name
            
            try:
                # 生成缩略图
                thumbnail_id = generate_thumbnail(temp_path, str(video_id))
                
                # 删除临时文件
                os.unlink(temp_path)
                
                return jsonify({
                    'success': True,
                    'video_id': str(video_id),
                    'thumbnail_id': thumbnail_id
                })
                
            except Exception as e:
                # 如果生成缩略图失败，确保清理临时文件
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise e
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            'thumbnail_url': f"/api/thumbnails/{str(video.get('thumbnail_id'))}" if video.get('thumbnail_id') else '',
            'file_path': video.get('file_path', '')
        } for video in videos]
        
        return jsonify({
            'success': True,
            'videos': video_list
        })
        
    except Exception as e:
        print(f"Error in get_videos: {str(e)}")
        return jsonify({'success': False, 'error': f'获取视频列表失败: {str(e)}'}), 500

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
            
        # 删除 GridFS 中的文件
        if 'file_id' in video:
            fs.delete(video['file_id'])
            
        # 删除缩略图
        if 'thumbnail_id' in video:
            fs.delete(video['thumbnail_id'])
            
        # 删除视频记录
        videos_collection.delete_one({'_id': ObjectId(video_id)})
        
        return jsonify({
            'success': True,
            'message': '视频删除成功'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'删除视频失败: {str(e)}'}), 500

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

        # 从 GridFS 获取视频文件
        if 'file_id' not in video:
            return jsonify({'error': 'Video file not found in database'}), 404
            
        # 创建临时目录
        user_temp_dir = os.path.join(tempfile.gettempdir(), f"user_{str(current_user['_id'])}")
        os.makedirs(user_temp_dir, exist_ok=True)

        # 将 GridFS 中的视频保存到临时文件
        temp_video_path = os.path.join(user_temp_dir, f"temp_video_{video_id}.mp4")
        with open(temp_video_path, 'wb') as temp_file:
            grid_file = fs.get(video['file_id'])
            temp_file.write(grid_file.read())

        try:
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

        # 从 GridFS 获取视频文件
        if 'file_id' not in video:
            return jsonify({'error': '视频文件不存在'}), 404
            
        grid_file = fs.get(video['file_id'])
        
        # 使用 send_file 发送视频文件
        return send_file(
            io.BytesIO(grid_file.read()),
            mimetype=grid_file.content_type,
            as_attachment=False,
            download_name=video['filename']
        )
        
    except Exception as e:
        print(f"获取视频错误: {str(e)}")
        return jsonify({'error': f'获取视频失败: {str(e)}'}), 500

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

# 更新指定场景
@app.route('/api/videos/<video_id>/scenes/<scene_id>', methods=['PUT'])
@token_required
def update_scene(current_user, video_id, scene_id):
    try:
        data = request.json
        
        # 添加日志以便调试
        # print(f"更新场景数据: {data}")
        # print(f"video_id: {video_id}, scene_id: {scene_id}")
        
        # 验证数据完整性
        if not all(key in data for key in ['scene_number', 'start_time', 'end_time', 'description']):
            return jsonify({'error': '缺少必要字段'}), 400
        
        update_query = {
            'video_id': ObjectId(video_id),
            'user_id': ObjectId(current_user['_id']),
            'scenes._id': ObjectId(scene_id)
        }
        
        update_operation = {
            '$set': {
                'scenes.$.scene_number': data.get('scene_number', ''),
                'scenes.$.start_time': data.get('start_time', '00:00:00.000'),
                'scenes.$.end_time': data.get('end_time', '00:00:00.000'),
                'scenes.$.description': data.get('description', ''),
                'updated_at': datetime.now()  # 添加更新时间
            }
        }
        
        # 添加日志以便调试
        # print(f"更新查询: {update_query}")
        # print(f"更新操作: {update_operation}")
        
        result = scripts_collection.update_one(update_query, update_operation)
        
        if result.matched_count == 0:
            return jsonify({'error': '未找到指定场景或无权访问'}), 404
            
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
        traceback.print_exc()  # 添加详细的错误追踪
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
def chat_endpoint(current_user):
    try:
        data = request.json
        message = data.get('message', '')
        image_data = data.get('image')
        
        # 添加日志以便调试
        print(f"Received request - message: {message[:100]}...")  # 只打印前100个字符
        
        if not message and not image_data:
            return jsonify({'error': 'Message or image is required'}), 400

        # 获取用户的最近历史对话（最近10条对话）
        try:
            chat_history = list(chat_history_collection.find(
                {'user_id': ObjectId(current_user['_id'])}
            ).sort('created_at', -1).limit(10))
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            chat_history = []

        # 构建历史消息列表（每条对话最多包含前后4轮对话）
        history_messages = []
        message_count = 0
        MAX_HISTORY_MESSAGES = 8  # 限制历史消息数量

        try:
            for chat in reversed(chat_history):  # 反转顺序以保持时间顺序
                for msg in chat['messages']:
                    if message_count >= MAX_HISTORY_MESSAGES:
                        break
                        
                    # 只添加文本内容，不包含图片以节省 tokens
                    content = msg.get('content', '')
                    if isinstance(content, list):  # 处理包含图片的消息
                        content = next((item.get('text', '') for item in content if item.get('type') == 'text'), '')

                    history_messages.append({
                        'role': msg.get('role', 'user'),
                        'content': content
                    })
                    message_count += 1
                
                if message_count >= MAX_HISTORY_MESSAGES:
                    break
        except Exception as history_error:
            print(f"History processing error: {str(history_error)}")
            history_messages = []

        # 调用 AI 助手，传入有限的历史记录
        try:
            result = chat_with_ai(message, image_data, history_messages)
            
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
                        'image': image_data,
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
        history = list(chat_history_collection.find(
            {'user_id': ObjectId(current_user['_id'])}
        ).sort('created_at', -1))  # 按时间倒序排列
        
        # 处理 ObjectId 为字符串
        for chat in history:
            chat['_id'] = str(chat['_id'])
            chat['user_id'] = str(chat['user_id'])
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        print(f"Get chat history error: {str(e)}")
        return jsonify({'error': f'Failed to get chat history: {str(e)}'}), 500
