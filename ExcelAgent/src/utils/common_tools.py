import re
import uuid
from typing import Dict, List, Callable,  List 
import json
from langgraph.prebuilt.interrupt import HumanInterruptConfig, HumanInterrupt
from langgraph.types import interrupt
from langchain_core.tools import tool as create_tool, BaseTool
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import Annotated, NotRequired, Sequence, TypedDict
from langchain_core.runnables import RunnableConfig
from langgraph.types import Send, interrupt
from langgraph.prebuilt.interrupt import HumanInterruptConfig, HumanInterrupt
import asyncio

def clear_image_history(_state):
    username = {'HumanMessage': 'user', 'AIMessage' : 'ai', 'ToolMessage': 'tool', 'SystemMessage': 'system'}
    new_state = []
    for message in _state['messages']:
        # print('清理的图片如下：')
        # print(message.__class__.__name__)
        # print(message.content)
        if message.__class__.__name__ == 'HumanMessage':
            is_image = False
            if isinstance(message.content, list):
                if(len(message.content) > 0):
                    for i_content in message.content:
                        if i_content['type'] == 'image' or i_content['type'] == 'image_url':
                            is_image = True
                            break
            if is_image:
                continue
        new_state.append(message)
    return new_state        

def merge_dict (dict1:Dict, dict2:Dict):
    merged_dict = {**dict1, **dict2}
    return merged_dict
def get_parameters(text: str):
    json_pattern = re.compile(r'```json\n(.*?)\n```', re.DOTALL)
    matches = json_pattern.findall(text)
    result = []
    for item in matches:
        # print(item)
        # input('查看是否符合json格式')
        try:
            result.append(json.loads(item))
        except:
            print(item)
            input()
            continue
        # print('load成功')
    return result

def get_final_toolmessages(ques:List):
    ind = -1
    while True:
        if -ind <= len(ques):
            if ques[ind-1].__class__.__name__ == 'ToolMessage':
                ind -= 1
            else:
                return ind
        else:
            return ind
def get_only_32():
    return str(uuid.uuid4())

def make_tool_call(ans:AIMessage):
    # input('请查看响应')
    # print(ans)
    # input('请查看响应')
    result = get_parameters(ans.content)

    # print(f'查看invalid_tool_calls:{ans.invalid_tool_calls}')
    # input('查看正则')
    # print(result)
    # input('查看正则')

    if result:
        ans.tool_calls =  ans.tool_calls if ans.tool_calls else []
        ans.additional_kwargs['tool_calls'] = ans.additional_kwargs.get('tool_calls', [])
        for ind, item_para in enumerate(result):
            # keys = list(item_para.keys())
            # value = list((item_para[key]))

            # ans.additional_kwargs['tool_calls'][ind]['function']['arguments'] = {key : value} # 这个arguments的参数是一个str，非常你逆天
            # input(item_para)
            name = item_para['name']
            args = item_para['arguments']
            # id = ans.additional_kwargs['tool_calls'][ind]['id']
            id = 'chatcmpl-tool-' + get_only_32().replace('-','',-1) # 14 + 32 = 46
            print(f'id:{id}, {len(id)}')
            type = 'tool_call'
            ans.tool_calls.append({'name':name, 'args':args, 'id':id, 'type':type})
            ans.invalid_tool_calls = []
        ans.response_metadata['finish_reason'] = 'tool_calls'
    if ans.invalid_tool_calls:
        print('意外的情况，快上报！！！')
        input('1111')
    # input(f'查看ans\n{[ans]}')
    # extend_ques2 = [HumanMessage(content = f'既然你已经知道要传递那些参数，请利用你之前回答的arguments，请重新调用以下工具函数:{valid_func_str},**【确保所有参rguments不为None】**！')]
    # ques += [ans] + extend_ques2 # + sys_prompt
    # ans = await llm_with_tools.ainvoke(ques)
    # input(f'查看ans\n{[ans]}')
    # input('查看改过自新的ans')
    # print([ans])
    # input('查看改过自新的ans')

    return ans

# (工具打断，人工在环) [https://github.langchain.ac.cn/langgraph/how-tos/human_in_the_loop/add-human-in-the-loop/?h=#add-interrupts-to-any-tool]
def add_human_in_the_loop(
    tool: Callable | BaseTool,
    *,
    interrupt_config: HumanInterruptConfig = None,
    TR: None
) -> BaseTool:
    """Wrap a tool to support human-in-the-loop review."""
    if not isinstance(tool, BaseTool):
        tool = create_tool(tool)
    if interrupt_config is None:
        interrupt_config = {
            "allow_accept": True,
            "allow_edit": True,
            "allow_respond": True,
            "allow_ignore": False
        }

    @create_tool(  
        tool.name,
        description=tool.description,
        args_schema=tool.args_schema
    )
    async def call_tool_with_interrupt(config: RunnableConfig, **tool_input):
        if tool.name + str(tool_input) in TR.tools_record:
            tool_response = TR.tools_record[tool.name + str(tool_input)]
            return tool_response
        request: HumanInterrupt = {
            "action_request": {
                "action": tool.name,
                "args": tool_input
            },
            "config": interrupt_config,
            "description": "Please review the tool call"
        }
        response = interrupt([request])[0]
        print(f'hhhh \n {response}')
        # approve the tool call
        if response["type"] == "accept":
            tool_response = await tool.ainvoke(tool_input, config)
            TR.tools_record[tool.name + str(tool_input)] = tool_response
        # update tool call args
        elif response["type"] == "edit":
            tool_input = response["args"]["args"]
            tool_response = await tool.ainvoke(tool_input, config)
            TR.tools_record[tool.name + str(tool_input)] = tool_response
        # respond to the LLM with user feedback
        elif response["type"] == "response":
            user_feedback = response["args"]
            tool_response = user_feedback
            TR.tools_record[tool.name + str(tool_input)] = tool_response
        else:
            raise ValueError(f"Unsupported interrupt response type: {response['type']}")

        return tool_response

    return call_tool_with_interrupt