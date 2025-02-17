from openai import OpenAI
import base64
import os

client = OpenAI(api_key="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")

def chat_with_ai(message, image_data=None, history=None):
    try:
        # 构建系统提示，专注于专业的音频描述并支持多种指南
        system_message = {
            "role": "system",
            "content": (
                "You are a professional AI assistant specializing in writing and refining audio descriptions (AD) "
                "for film and television. Your goal is to create clear, concise, and accurate AD that enhances "
                "accessibility for blind and visually impaired audiences.\n\n"
                
                "You must respond based on users' questions, offering suggestions, improvements, and explanations "
                "while maintaining an objective, professional, and user-friendly tone. Your responses should align "
                "with industry best practices (e.g., clarity, neutrality, immersive storytelling) and, where applicable, "
                "adjust to specific AD guidelines based on the user's preference (e.g., Ofcom, FCC, WGBH, ADLAB PRO, "
                "Netflix AD Style Guide).\n\n"
                
                "If a user does not specify a guideline, provide recommendations based on general industry standards. "
                "If they do specify a guideline, tailor your response accordingly while maintaining core principles "
                "of effective AD."
            )
        }
        
        # 构建消息历史
        messages = [system_message]
        
        # 添加历史对话
        if history:
            for msg in history:
                messages.append({
                    "role": "user" if msg['role'] == 'user' else "assistant",
                    "content": msg['content']
                })
        
        # 添加当前消息
        if image_data:
            # 处理图片，将base64转换为OpenAI需要的格式
            base64_image = image_data.split(',')[1] if ',' in image_data else image_data
            
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": message
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            })
        else:
            # 纯文本对话
            messages.append({
                "role": "user",
                "content": message
            })

        # 统一使用 gpt-4-mini 模型
        completion = client.chat.completions.create(
            model="gpt-4o-mini",  # 使用统一的模型
            messages=messages,
            max_tokens=1000,  # 保持较高的 token 限制以获取完整的描述
            temperature=0.5,  # 保持较低的温度以确保专业性和准确性
        )

        return {
            'success': True,
            'response': completion.choices[0].message.content
        }

    except Exception as e:
        print(f"AI Assistant error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
