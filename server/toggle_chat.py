from openai import OpenAI
from datetime import datetime, UTC

client = OpenAI(api_key="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")

def handle_scene_chat(current_text, user_message, chat_histories=None):
    try:
        system_prompt = """You are a professional AI assistant specialising in writing and refining audio descriptions (AD) for film and television. 
Your goal is to create clear, concise, and accurate AD that enhances accessibility for blind and visually impaired audiences.

The current scene text is: {current_text}

Please help modify or improve the description for current scene text based on the user's requirements while maintaining an objective, professional, and user-friendly tone."""

        # 构建消息列表
        messages = [
            {
                "role": "system", 
                "content": system_prompt.format(current_text=current_text)
            }
        ]
        
        # 如果有历史消息，添加到消息列表
        if chat_histories:
            messages.extend(chat_histories)
            
        # 添加当前用户消息
        messages.append({
            "role": "user", 
            "content": user_message
        })

        # 调用 OpenAI API
        response = client.chat.completions.create (
            model="gpt-4o-mini",
            messages=messages
        )
        
        ai_message = response.choices[0].message.content
        print("AI response:", ai_message)
        
        # 返回完整的消息列表，包括系统消息、历史消息和新消息
        return {
            'success': True,
            'message': ai_message,
        }
        
    except Exception as e:
        print(f"Error in handle_scene_chat: {str(e)}")
        return {
            'success': False,
            'error': f'AI processing failed: {str(e)}'
        }
