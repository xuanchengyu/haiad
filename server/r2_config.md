# Cloudflare R2 配置说明

## 1. 获取R2配置信息

在Cloudflare R2控制台获取以下信息：
- **Access Key ID**: R2访问密钥ID
- **Secret Access Key**: R2访问密钥
- **Account ID**: 账户ID
- **Bucket Name**: 存储桶名称
- **Public URL**: 公共访问URL（可以是自定义域名或R2提供的URL）

## 2. 设置环境变量

在服务器上设置以下环境变量：

```bash
export R2_ACCESS_KEY_ID="your-r2-access-key-id"
export R2_SECRET_ACCESS_KEY="your-r2-secret-access-key"
export R2_ACCOUNT_ID="your-r2-account-id"
export R2_BUCKET_NAME="your-r2-bucket-name"
export R2_PUBLIC_URL="https://your-custom-domain.com"
```

## 3. 安装依赖

```bash
pip install boto3
```

## 4. 测试配置

启动服务器后，上传一个视频文件测试R2连接是否正常。

## 注意事项

- 确保R2存储桶已创建并配置了正确的权限
- 如果使用自定义域名，需要配置DNS解析
- 建议在生产环境中使用环境变量而不是硬编码配置 