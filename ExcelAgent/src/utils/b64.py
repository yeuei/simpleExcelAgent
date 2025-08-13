import re
import base64
def is_base64(s):
    # Base64正则表达式模式（包含标准集和URL安全集）
    pattern = r'^[A-Za-z0-9+/]*={0,2}$|^[A-Za-z0-9-_]*={0,2}$'
    
    # 检查基本条件
    if not isinstance(s, str) or len(s) % 4 != 0:
        return False
    
    # 检查字符集是否合法
    if not re.fullmatch(pattern, s):
        return False
    
    # 尝试解码验证（可选但更严格）
    try:
        decoded = base64.b64decode(s, validate=True)
        # 验证可逆性（可选）
        re_encoded = base64.b64encode(decoded).decode()
        return s.rstrip('=') == re_encoded.rstrip('=')
    except:
        return False