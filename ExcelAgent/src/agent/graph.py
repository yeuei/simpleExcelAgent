# 导入包是在Agent 目录下进行的
from dataclasses import dataclass
import operator
from typing import Dict, List, Optional, Tuple, Union
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage, RemoveMessage
from langchain_core.tools import tool
import langgraph
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.graph.message import add_messages
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Send
from typing_extensions import Sequence, TypedDict, Annotated
from langgraph.prebuilt import ToolNode, tools_condition
from StructureOutput.structure_output_agent import StructureAgent, Image_Text_depature
from langchain_core.messages import HumanMessage
from utils import Connect, b64
import base64
import os
import re
import json
from langchain_experimental.utilities import PythonREPL
from utils.common_tools import clear_image_history, make_tool_call, get_final_toolmessages, add_human_in_the_loop
import aiofiles
from functools import partial

@dataclass
class Tools_record():
    tools_record = {}
TR1 = Tools_record()
TR2 = Tools_record()

TR1.tools_record = {}
TR2.tools_record = {}

TR1_LOOP = partial(add_human_in_the_loop, TR = TR1)
TR2_LOOP = partial(add_human_in_the_loop, TR = TR2)



repl = PythonREPL()
@tool
def python_repl_tool(
    code: Annotated[str, "The python code to execute to generate your chart."],
):
    # """Use this to execute python code. If you want to see the output of a value,
    # you should print it out with `print(...)`. This is visible to the user."""
    """
    如果需要读取图片，请注意：你自己具有读取图片的能力，不能使用工具读取图片
    使用此功能执行Python代码。如果你想查看某个值的输出,应该使用 print(...) 将其打印出来。这样用户就能看到输出结果。
    只有在其他工具都无法满足用户要求的情况下才能使用该工具!注意当前环境下还配备excel工具, 所以一旦涉及到excel操作先查看是否有excel工具可以满足任务需求。
    """
    try:
        result = repl.run(code)
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"
    result_str = f"Successfully executed:\n\`\`\`python\n{code}\n\`\`\`\nStdout: {result}"
    return (
        result_str + "\n\nIf you have completed all tasks, respond with FINAL ANSWER."
    )

# 对话记忆存储点
memory = MemorySaver()
# 对话记忆线程
config = {"configurable": {"thread_id": "1", "check_new_photo": True, "max_interaction": 2}}

@dataclass
class Global_var():
    check_new_photo = True
    max_interaction = 2 # AI和工具最多交互5轮
gvar = Global_var()
gvar.check_new_photo = True
gvar.max_interaction = 2




# 定义客户端
async def get_all_tools_bylang():
    client = MultiServerMCPClient(
        {
            "weather":{
                "url": "http://localhost:8009/mcp",
                "transport" : "streamable_http"
            },
            "excel":{
                "url": "http://localhost:8017/mcp",
                "transport" : "streamable_http"
            }
        }
    )
    tools = await client.get_tools()
    return tools

all_tools = asyncio.run(get_all_tools_bylang())
all_tools.append(python_repl_tool)
# 获得模型
# print(all_tools)
# input('wait')

# input(all_tools)
qwen_vl_llm = Connect.get_llm()

# 获得structure 模型
async def get_prompt():
    async with aiofiles.open('prompt/image_text_depature.txt', 'r') as f:
        prompt = await f.read()
    return prompt
prompt = asyncio.run(get_prompt())


all_tools1 = [TR1_LOOP(tool) for tool in all_tools]
all_tools2 = [TR2_LOOP(tool) for tool in all_tools]
# 绑定模型
# llm_with_tools = qwen_vl_llm.bind_tools(all_tools)
llm_with_tools1 = qwen_vl_llm.bind_tools(all_tools1)
llm_with_tools2 = qwen_vl_llm.bind_tools(all_tools2)


image_partial_agent = StructureAgent(qwen_vl_llm, prompt, Image_Text_depature)
# 定义状态
class MyState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages] = []
    photos: List[str] = []
    image_question: str
    text_question: str
    recursion_times:int = 0
    

class SubState(TypedDict): # 子图状态
    new_messages:Annotated[List, add_messages] = []
    sub_question: str
    photos:List[str]
    recursion_times:int = 0

# 或者继承标准MessagesState
class BriefState(MessagesState):
    photos: list[str] = []


'''
子图
'''
################################################################################

# 自定义消息
def recursion_counter(state, config:RunnableConfig):
    state['recursion_times'] += 1
    return {'recursion_times': state['recursion_times']}

def subgraphs_condition(state):
    print(f'当前调用tool的次数{state["recursion_times"]}')
    if state['recursion_times'] > gvar.max_interaction:
    # if state['recursion_times'] > config['configurable']['max_interaction']:
        return '__end__'
    return tools_condition(state, messages_key="new_messages")

sub_tool_node1 = ToolNode(tools = all_tools1, messages_key = 'new_messages')
sub_tool_node2 =ToolNode(tools = all_tools2, messages_key = 'new_messages')

async def only_text_chat(_state:SubState):
    count = 0
    # 强制使用tool_calls
    async with aiofiles.open('./prompt/tools_arguments.txt', 'r') as f:
        arguments_shedule = await f.read()
    sys_prompt = [SystemMessage(content = f'{arguments_shedule}')]# 如果需要使用Sheet1但是没有Sheet1,请创建Sheet1;如果Sheet1已经存在,禁止删除该Sheet1,可以直接在上面操作**')]
    
    if _state.get('messages', False):
        input('不可能123！')
        ques = _state['messages'].copy()
        count += 1
    if _state.get('new_messages', False):
        # assert isinstance(_state, TempState), '撕，不可能2！上报'
        ques = _state['new_messages'].copy()
        count += 1
    assert count == 1, '不太对'

    guodu_message = HumanMessage(
        content = '\n\n以上内容全部为历史信息\n\n' 
    )

    if _state.get('sub_question', False):
        ques += [guodu_message] + [HumanMessage(content = '请结合历史信息完成你的任务，现在你的任务是' + _state['sub_question'] + '请一步一步实现这个任务，每一步都要展现出来！')]
    # 强制使用tool_calls
    if len(ques) != 0 and ques[-1].__class__.__name__ == 'ToolMessage':
        ind = get_final_toolmessages(ques)
        # input('出现了！！！！')
        ques = ques[:ind] + sys_prompt + ques[ind:]
    else:
        ques += sys_prompt
    ans = await llm_with_tools1.ainvoke(ques)
    TR1.tools_record.clear()
    new_ans =  make_tool_call(ans)
    return {"new_messages": [new_ans], 'sub_question': ''}

async def multi_process(_state:SubState):
    # 将图片集中在一起
    photo_inputs = []
    for ph in _state['photos']:
        photo_inputs.append({
            "type": "image",
            "source_type": "base64",
            "data": ph,
            "mime_type": "image/png",
        })
    async with aiofiles.open('./prompt/tools_arguments.txt', 'r') as f:
        arguments_shedule = await f.read()
    sys_prompt = [SystemMessage(content = f'{arguments_shedule}')]

    guodu_message = HumanMessage(
        content = '\n\n以上内容全部为历史信息\n\n以下内容是用户迄今为止上传的图片\n\n' 
    )
    multimodal_message = HumanMessage(
            content = photo_inputs
    )
    # assert _state.get('sub_question', False), '能进来就不可能为空2' # 注意sub_question只能用一次，之后都是在子图中和tools交流
    text_message = HumanMessage(
            content = '结合历史信息和图片，现在你的任务是' + _state.get('sub_question', '')+ '请一步一步实现这个任务，每一步都要展现出来！'
    )
    if 'new_messages' in _state.keys():
        ques = _state['new_messages'].copy()
    elif _state.get('messages', False):
        input('不可能321！')
        ques = clear_image_history(_state)
    else:
        input('撕，不太可能啊，快上报错误！！！')
    
    # input('请查看抽取图片后的内容')
    # print(ques)
    # input('请查看抽取图片后的内容')

    if _state.get('sub_question', False): # 为True
        ques += [guodu_message]+ [multimodal_message] + [text_message] + sys_prompt

    # 理论上_state.get('sub_question', False)为False的时候，就是已经在子图循环过至少一次了，
    # 那么就可以只管工具调用了  
    if len(ques) != 0 and ques[-1].__class__.__name__ == 'ToolMessage':
        ind = get_final_toolmessages(ques)
        # ques = ques[:ind] + [guodu_message]+ [multimodal_message] + [text_message] + sys_prompt + ques[ind:]
        ques = ques[:ind] + [guodu_message]+ [multimodal_message] + sys_prompt + ques[ind:]
    else:
        ques += [guodu_message] + [multimodal_message] + sys_prompt

    # input('当前的ques')
    # print(ques)
    # input('当前的ques')
    ans = await llm_with_tools2.ainvoke(ques)
    new_ans =  make_tool_call(ans)
    TR2.tools_record.clear()
    return {"new_messages": [new_ans], 'sub_question': ''}

# 纯文本子图
subgraph_text = StateGraph(SubState)
subgraph_text.add_node('only_text_chat', only_text_chat)
subgraph_text.add_node('sub_tool_node1', sub_tool_node1)
subgraph_text.add_node('recursion_counter1', recursion_counter)

subgraph_text.add_edge(START, 'only_text_chat')
subgraph_text.add_edge('sub_tool_node1', 'only_text_chat')
subgraph_text.add_edge('only_text_chat','recursion_counter1')
subgraph_text.add_conditional_edges('recursion_counter1', subgraphs_condition, path_map={'tools': 'sub_tool_node1', '__end__': END})

# 多模态子图
subgraph_multi = StateGraph(SubState)
subgraph_multi.add_node('multi_process', multi_process)
subgraph_multi.add_node('sub_tool_node2', sub_tool_node2)
subgraph_multi.add_node('recursion_counter2', recursion_counter)

subgraph_multi.add_edge(START, 'multi_process')
subgraph_multi.add_edge('sub_tool_node2', 'multi_process')
subgraph_multi.add_edge('multi_process','recursion_counter2')
subgraph_multi.add_conditional_edges('recursion_counter2', subgraphs_condition, path_map={'tools': 'sub_tool_node2', '__end__': END})

# 内部自带记忆
subgraph_multi = subgraph_multi.compile() # checkpointer=True
subgraph_text = subgraph_text.compile() # checkpointer=True

'''
主图
'''
###########################################################
def upload_photo(_state:MyState, config: RunnableConfig):
    if not _state.get('photos', False):
        _state['photos'] = []
    # input(f'_state {_state}')
    for t_message in _state['messages']:
        if t_message.__class__.__name__ == 'HumanMessage':
            if isinstance(t_message.content, list):
                if len(t_message.content) > 0:
                    for data in t_message.content:
                        if data['type'] == 'image':
                            _state['photos'].append(data['data'])
                            gvar.check_new_photo = True
                        if data['type'] == 'image_url':
                            _state['photos'].append(data['image_url']['url'].split('base64,')[-1])
                            gvar.check_new_photo = True
    return {"photos":_state['photos']}


def check_format(_state:MyState):
    new_photos = []
    goto = 'check_together_deal'
    if _state.get("photos", False): # and gvar.check_new_photo : #有新图片且图片存在
        # 包含图片先进行图片处理
        for photo in _state["photos"]:
            # 全部转换为base64
            if not b64.is_base64(photo):
                # 那么为路径
                photo = Connect.get_base64(photo)
            new_photos.append(photo)
    else:
        print('goto only_text_chat_sub')
        goto = 'only_text_chat_sub'
    return {"photos":new_photos, 'recursion_times':0}

def goto_where(_state) -> Union['check_together_deal', 'only_text_chat_sub']:
    if _state.get("photos", False):
        return 'check_together_deal'
    else:
        return 'only_text_chat_sub'

async def check_together_deal(_state:MyState, config: RunnableConfig):

    """
     temp = _state['messages'] 是引用赋值，如果改变temp会引起全局_state的改变
     比如
     temp[0] = AIMessage(content = '大帅哥')
     那么就算在returen的时候更新了`messages`参数，也会导致_state['messages']的第一个元素是AIMessage(content = '大帅哥')
    """
    # temp = _state['messages'] 

    photo_inputs = []
    if gvar.check_new_photo:
        gvar.check_new_photo = False
        for photo in _state["photos"]:
            photo_inputs.append({
                "type": "image",
                "source_type": "base64",
                "data": f"{photo}",
                "mime_type": "image/png",
            })
    if photo_inputs:
        # print('有新图片')
        multimodal_message = [HumanMessage(
                content = photo_inputs
        )]
    else:
        multimodal_message = []


    text_message = SystemMessage(
            content =  '\n\n以上内容为历史信息\n\n以下内容是用户的问题:\n\n'  
                        + str(_state['messages'][-1].content)
                        + '\n\n接下来需要你对用户问题进行处理,以下是处理规则:\n\n'
                        + image_partial_agent.sys_prompt
    )

    history_messages = clear_image_history(_state)

    all_history = history_messages[:-1] + [text_message]  #  _state['messages'][:-1] + [text_message]    
    async with aiofiles.open('final_history.txt', 'w') as f:
        await f.write(str(all_history))
    
    print('开始invoke')
    ans = await image_partial_agent.llm_struture.ainvoke(all_history)
    print('结束invoke')
    print(ans)

    return{
        'image_question':ans.image_question,
        'text_question':ans.text_question,
    }



def go_to_multi_process(_state:MyState):
    # 对提问消息进行裁剪
    new_messages = []
    # input([_state['messages'][-1] ])
    if _state['messages'][-1].__class__.__name__ == 'HumanMessage':
        if isinstance(_state['messages'][-1].content, list) and (len(_state['messages'][-1].content) > 0):
            last_is_image = False
            for i_content in _state['messages'][-1].content:
                if i_content['type'] == 'image' or i_content['type'] == 'image_url':
                    last_is_image = True
                    break
            if last_is_image:
                new_messages = _state['messages'][:-2] + [_state['messages'][-1]] # 跳过上一条文字信息
        else:
            new_messages = _state['messages'][:-1] # 上一条就是文字信息，所以要跳过
    assert len(new_messages) > 0, 'new_messages 不能为空'

    map_list:List[Send] =  []
    if _state['image_question']:
        # new_state_messages = clear_image_history(_state)
        # new_state_messages = new_state_messages[:-1] # 裁剪混合消息
        new_state_messages = new_messages.copy()
        map_list.append(Send(
            'multi_process_sub',
            {
                'new_messages': new_state_messages, # 切片就是copy()
                'sub_question': _state['image_question'],
                'photos':_state['photos'], # 为了重新吸引图片注意力
                'recursion_times': 0
            }
        ))
    if _state['text_question']:
        map_list.append(Send(
            'only_text_chat_sub',
            {
                'new_messages': new_messages, # 自带了photos
                'sub_question': _state['text_question'],
                'recursion_times': 0
            }
        ))
    return map_list

async def only_text_chat_sub(_state):

    assert not (_state.get('new_messages', False) and _state.get('messages', False)), 'new_messages和messages不能同时存在'
    
    # 消息记录
    res = {}
    if _state.get('new_messages', False): # 从got_to_multi_process Send过来 ||| 子图内部循环

        print(_state.keys()) # ['new_messages', 'sub_question']
        print('现在是子图only_text_chat_sub')
        print('='*50) 
        res = await subgraph_text.ainvoke(_state)     
    elif _state.get('messages', False): # 从check_format直接过来
        print(_state.keys()) # ['messages', 'photos']
        print('从check_format直接过来,现在是子图only_text_chat_sub')
        print('='*50)
        res = await subgraph_text.ainvoke({'new_messages' : _state['messages'].copy(), "recursion_times":_state['recursion_times']})  
    
    return {'messages' : res['new_messages']} # 返回最后的ai_message

async def multi_process_sub(_state):
    # 只有可能是new_message
    assert not _state.get('messages', False), 'multi_process_sub不可能有messages字段'
    print(_state.keys()) # dict_keys(['new_messages', 'sub_question', 'photos'])
    print('只能从check_together_deal过来')
    print('='*50)
    res = await subgraph_multi.ainvoke(_state)
    return {'messages' : res['new_messages']}

async def check_final_state(_state:MyState):
    async with aiofiles.open('final_state.txt', 'w') as f:
        await f.write(str(_state))
    print('final_state.txt,查看最终状态')

# 构件图
app = StateGraph(MyState)

app.add_node('upload_photo', upload_photo)
app.add_node('check_format', check_format)
app.add_node('check_together_deal', check_together_deal)
app.add_node('only_text_chat_sub', only_text_chat_sub)
app.add_node('multi_process_sub', multi_process_sub)
app.add_node('check_final_state', check_final_state)

app.add_edge(START, 'upload_photo')
app.add_edge('upload_photo', 'check_format')
app.add_conditional_edges('check_format', goto_where, path_map = {'check_together_deal': 'check_together_deal', 'only_text_chat_sub': 'only_text_chat_sub'})
# 添加工具条件边
# app.add_conditional_edges('only_text_chat', tools_condition, path_map = {'tools': 'tools_node', "__end__": 'check_final_state' })
# app.add_edge('tools_node', 'only_text_chat')
# 添加工具条件边
# app.add_conditional_edges('multi_process', tools_condition, path_map = {'tools': 'another_tools_node', "__end__": 'check_final_state' })
# app.add_edge('another_tools_node', 'multi_process')

app.add_conditional_edges('check_together_deal', go_to_multi_process, path_map = {'multi_process': 'multi_process_sub', 'only_text_chat': 'only_text_chat_sub'})

app.add_edge('only_text_chat_sub', 'check_final_state')
app.add_edge('multi_process_sub', 'check_final_state')
app.add_edge('check_final_state', END)

# 加入记忆和全局变量config


# 
graph = app.compile()
Connect.draw_flow(graph)


