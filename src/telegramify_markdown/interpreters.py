from typing import List, Any, Callable

import mistletoe

from telegramify_markdown.logger import logger
from telegramify_markdown.mermaid import render_mermaid
from telegramify_markdown.mime import get_filename
from telegramify_markdown.type import TaskType, File, Text, Photo, SentType


class BaseInterpreter(object):
    name = "base"

    def merge(self, tasks: List[TaskType]) -> List[TaskType]:
        """
        Merge the tasks.
        :param tasks:  [(base, [(token1,token2),(token1,token2)]), (base, [(token1,token2),(token1,token2)])]
        :return:
        """
        return tasks

    def split(self, task: TaskType) -> List[TaskType]:
        """
        Split the task.
        :param task: (base, [(token1,token2),(token1,token2)])
        :return: [(base, [(token1,token2),(token1,token2)]),....newTask]
        """
        return [task]

    def render_task(self,
                    task: TaskType,
                    render_block_func: Callable[[List[Any]], str],
                    render_lines_func: Callable[[str], str],
                    max_word_count: int = 4090
                    ) -> SentType:
        """
        Render the task.
        :param render_block_func: The render block function
        :param render_lines_func: The render lines function
        :param task: (base, [(token1,token2),(token1,token2)])
        :param max_word_count: The maximum number of words in a single message.
        :return: SentType
        """
        task_type, token_pairs = task
        if task_type != "base":
            logger.warn("Invalid task type for BaseInterpreter.")
        token1_l = list(__token1 for __token1, __token2 in token_pairs)
        token2_l = list(__token2 for __token1, __token2 in token_pairs)
        # 处理超过最大字数限制的情况
        if len(render_block_func(token1_l)) > max_word_count:
            # 如果超过最大字数限制
            if all(isinstance(_per_token1, mistletoe.block_token.CodeFence) for _per_token1 in token1_l) and len(
                    token1_l) == 1 and len(token2_l) == 1:
                # 如果这个 pack 是完全的 code block，那么采用文件形式发送。否则采用文本形式发送。
                _escaped_code = token1_l[0]
                _unescaped_code_child = list(token1_l[0].children)
                file_content = render_block_func(token2_l)
                if _unescaped_code_child:
                    _code_text = _unescaped_code_child[0]
                    if isinstance(_code_text, mistletoe.span_token.RawText):
                        file_content = _code_text.content
                lang = "txt"
                if isinstance(_escaped_code, mistletoe.block_token.CodeFence):
                    lang = _escaped_code.language
                """
                if lang.lower() == "mermaid":
                    try:
                        image_io, caption = render_mermaid(file_content.replace("```mermaid", "").replace("```", ""))
                        return [Photo(file_name="mermaid.png", file_data=image_io.getvalue(), caption=caption)]
                    except Exception as e:
                        pass
                """
                file_name = get_filename(line=render_block_func(token1_l), language=lang)
                return [File(file_name=file_name, file_data=file_content.encode(), caption="")]
            # 如果超过最大字数限制
            return [File(file_name="letter.txt", file_data=render_block_func(token2_l).encode(), caption="")]
        # 没有超过最大字数限制
        return [Text(content=render_block_func(token1_l))]


class MermaidInterpreter(BaseInterpreter):
    name = "mermaid"

    def merge(self, tasks: List[TaskType]) -> List[TaskType]:
        """
        Merge the tasks.
        :param tasks:  [(base, [(token1,token2),(token1,token2)]), (base, [(token1,token2),(token1,token2)])]
        :return:
        """
        return tasks

    def split(self, task: TaskType) -> List[TaskType]:
        """
        Split the task.
        :param task: (base, [(token1,token2),(token1,token2)])
        :return: [(mermaid, [(token1,token2),(token1,token2)]),....newTask]
        """
        task_type, token_pairs = task
        # 只处理 base 块
        if task_type != "base":
            return [task]
        # 用于存放生成的新任务
        tasks = []
        # 临时缓存非 Mermaid 块
        current_base_tokens = []
        for token_pair in token_pairs:
            token1, _ = token_pair
            # 检查是否为 Mermaid 块
            if isinstance(token1, mistletoe.block_token.CodeFence) and token1.language.lower() == "mermaid":
                if current_base_tokens:
                    # 将缓存的非 Mermaid 块生成新的 base 任务
                    tasks.append(("base", current_base_tokens))
                    current_base_tokens = []
                # 单独添加 Mermaid 块任务
                tasks.append(("mermaid", [token_pair]))
            else:
                # 累积 base 块
                current_base_tokens.append(token_pair)
        # 处理剩余的 base 块
        if current_base_tokens:
            tasks.append(("base", current_base_tokens))
        return tasks

    def render_task(self,
                    task: TaskType,
                    render_block_func: Callable[[List[Any]], str],
                    render_lines_func: Callable[[str], str],
                    max_word_count: int = 4090
                    ) -> SentType:
        """
        Render the task.#
        :param task: (base, [(token1,token2),(token1,token2)])  of [(base, [(token1,token2),(token1,token2)]), (base, [(token1,token2),(token1,token2)])]
        :param render_block_func: The render block function
        :param render_lines_func: The render lines function
        :param max_word_count: The maximum number of words in a single message.
        :return: SentType
        """
        task_type, token_pairs = task
        if task_type != "mermaid":
            raise ValueError("Invalid task type for MermaidInterpreter.")
        # 仅处理 Mermaid 块
        if len(token_pairs) != 1:
            raise ValueError("Invalid token length for MermaidInterpreter.")
        token1_l = list(__token1 for __token1, __token2 in token_pairs)
        token2_l = list(__token2 for __token1, __token2 in token_pairs)
        if not all(isinstance(_per_token, mistletoe.block_token.CodeFence) for _per_token in token1_l):
            raise ValueError("Invalid token type for MermaidInterpreter.")
        _escaped_code = token2_l[0]
        if (isinstance(
                _escaped_code,
                mistletoe.block_token.CodeFence
        ) and _escaped_code.language.lower() == "mermaid"):
            file_content = render_block_func(token1_l)
            _unescaped_code_child = list(_escaped_code.children)
            if _unescaped_code_child:
                _raw_text = _unescaped_code_child[0]
                if isinstance(_raw_text, mistletoe.span_token.RawText):
                    file_content = _raw_text.content
            try:
                img_io, url = render_mermaid(file_content.replace("```mermaid", "").replace("```", ""))
                message = f"[edit in mermaid.live]({url})"
            except Exception as e:
                return [
                    File(
                        file_name="mermaid_code.txt",
                        file_data=render_block_func(token2_l).encode(),
                        caption=""
                    )
                ]
            else:
                return [
                    Photo(
                        file_name="mermaid.png",
                        file_data=img_io.getvalue(),
                        caption=render_lines_func(message)
                    )
                ]
        return [
            File(file_name="mermaid_code.txt", file_data=render_block_func(token2_l).encode(), caption="")
        ]


Interpreters = [BaseInterpreter(), MermaidInterpreter()]