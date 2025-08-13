"""
qwen-2.5-vl-7b 启动参数
↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
export CUDA_VISIBLE_DEVICES=0 && \
vllm serve /home/25-fengyuan/LLModel/Qwen2.5-VL-7B-Instruct \
--host 0.0.0.0 --port 8000 --served-model-name Qwen2.5-VL-7B-Instruct \
--enable-auto-tool-choice --tool-call-parser hermes \
--max-model-len 16384 --limit-mm-per-prompt image=4 \
--allowed-local-media-path "/home/25-fengyuan/gitcode" \
--chat-template-content-format openai \
--generation-config vllm \
--chat-template /home/25-fengyuan/LLModel/qwen2.5_tool_chat_template.jinja

export CUDA_VISIBLE_DEVICES=1 && \
vllm serve /home/25-fengyuan/LLModel/Nous-Hermes-2-Vision-Alpha \
--host 0.0.0.0 --port 8001 --served-model-name Nous-Hermes-2-Vision-Alpha \
--enable-auto-tool-choice --tool-call-parser hermes \
--max-model-len 16384 --limit-mm-per-prompt image=2 \

"""
import langgraph.graph
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

from httpx import stream
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import argparse
import base64


# 返回兼容Openai格式的llm
def get_llm(base_url = 'http://localhost:8000/v1', api_key = 'none', model_name = 'Qwen2.5-VL-7B-Instruct'):
    return ChatOpenAI(
                model= model_name ,# 'qwen2.5-vl-72b-instruct', # model_name 
                # google/gemma-3-27b-it:free
                temperature=0,
                max_tokens=4096,
                timeout=50,
                max_retries=2,
                base_url= base_url,
                #'https://dashscope.aliyuncs.com/compatible-mode/v1', # base_url,
                # "https://generativelanguage.googleapis.com/v1beta/openai/"
                api_key= 'sk-59b6c13b9a4f48d4b69a5cf70b4f045e',
                #'sk-59b6c13b9a4f48d4b69a5cf70b4f045e', # api_key,
                # AIzaSyD8NLPmap9jCK9lfwtyuYp5DNhnHgFgQ1I
                streaming=True
                )
def get_base64(local_url:str):
    with open(local_url, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode("utf-8")
    return image_data

def draw_flow(graph:langgraph.graph.state.CompiledStateGraph, save_path = None):
    try:
        # 使用 Mermaid 生成图表并保存为文件
        mermaid_code = graph.get_graph().draw_mermaid_png()
        if save_path is None:
            save_path = 'graph.jpg'
        with open(save_path, "wb") as f:
            f.write(mermaid_code)

        # 使用 matplotlib 显示图像
        img = mpimg.imread(save_path)
        plt.imshow(img)
        plt.axis('off')  # 关闭坐标轴
        if(save_path is not None):
            plt.savefig(save_path)
        plt.show()
    except Exception as e:
        print(f"报错： {e}")