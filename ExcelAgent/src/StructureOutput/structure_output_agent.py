from langchain.prompts import ChatMessagePromptTemplate
from pydantic import BaseModel, Field
from abc import abstractmethod
from typing import List, Dict


class ImagePartial(BaseModel):
    image_partition: Dict[str, List[int]] = Field(
        description="键为分组描述，值为图片索引列表。例如：{'灾害现场图片': [1, 3], '财产损失表格': [2], '联合所有图片分析': [1, 2, 3]}"
    )   
    sub_questions: List[str] = Field(
        description="与image_partition中的分组一一对应的子问题列表。例如:['请结合图片信息，说明灾害的原因和损失', '请结合表格信息，说明灾害造成的财产损失情况']"
    )
    pure_text_question: List[str] = Field(
        description="与图片无关的纯文本子问题列表。例如:['请分析灾害发生的主要原因', '请评估此次灾害对当地经济的长期影响']。如果没有此类问题，请设为 ['Null']"
    )
class Image_Text_depature(BaseModel):
    COT:str = Field(description = '这里是包含【问题重述】和【依赖链归属】两个部分的、导致最终分解结果的结构化思考过程。')
    sound_question: str = Field( description="这里是经过上下文补全、消除歧义后的完整、健全的任务指令。image_question和text_question不能同时为空, 且image_question+text_question=sound_question")
    text_question: str = Field( description="这里是仅凭文本就能完成的任务描述，如果不存在则留空。")
    image_question: str = Field( description="这里是需要看图才能完成的任务描述，如果不存在则留空。")
    

class StructureAgent():
    def __init__(self, llm, prompt, StrutureClass:BaseModel) -> None:
        self.sys_prompt = prompt
        self.StrutureClass = StrutureClass
        self.llm_struture = llm.with_structured_output(self.StrutureClass)
        del prompt
        del StrutureClass
    def __name__(self) -> str:
        return f"prompt:{self.sys_prompt}, Structure:{StrutureClass}"
    