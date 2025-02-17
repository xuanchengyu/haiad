import pymongo
from gridfs import GridFS

mongo_uri = "mongodb+srv://juneyxc:GzJjSY7HzROoZrWZ@haiad.jscuo.mongodb.net/?retryWrites=true&w=majority&appName=haiad"
client = pymongo.MongoClient(mongo_uri)
db = client["haiad"]
fs = GridFS(db)

# ✅ 查看 `fs.files` 是否有视频
# print("✅ GridFS 里存储的文件:", fs.list())

# # ✅ 获取文件 ID
# file_id = "67b3b1305368156d24c24293"

# # ✅ 检查 `fs.chunks` 是否有该文件的分片数据
# chunks_count = db.fs.chunks.count_documents({"files_id": file_id})
# print(f"✅ GridFS 里的 `chunks` 数量: {chunks_count}")

# from pymongo import MongoClient
# from gridfs import GridFS

# mongo_uri = "your-mongodb-atlas-uri"
# client = MongoClient(mongo_uri)
# db = client["your-database"]
# fs = GridFS(db)

# # ✅ 上传一个测试文件
# try:
#     file_id = fs.put(b"Hello GridFS", filename="test.txt")
#     print("✅ `fs.put()` 成功，file_id:", file_id)

#     # ✅ 检查 `fs.chunks` 里是否有数据
#     chunks_count = db.fs.chunks.count_documents({"files_id": file_id})
#     print(f"✅ GridFS `fs.chunks` 里存储的块数量: {chunks_count}")

# except Exception as e:
#     print("❌ `fs.put()` 失败:", str(e))

videos_collection = db['videos']  

video = videos_collection.find_one({}, {"_id": 1, "file_id": 1})
print("✅ `videos_collection` 里的数据:", video)