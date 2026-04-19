# services/pir_server/engine_adapter.py
import sys
import asyncio
import json
import uuid
from pathlib import Path
import logging


# 细分桥接层异常
class EngineNotFoundError(Exception): pass


class EngineTimeoutError(Exception): pass


class EngineProcessError(Exception): pass


class EngineProtocolError(Exception): pass


class EngineResponseError(Exception): pass


# 声明局部 logger
logger = logging.getLogger("pir_server")


async def call_external_pir_engine(engine_cmd: list, timeout_sec: float, query_payload: str, working_dir: str = "") -> \
tuple[str, dict]:
    """
    返回: (result_str, engine_meta_dict)
    """
    root_path = Path(__file__).resolve().parent.parent.parent

    # 小修 B: 工作目录绝对路径展开收口
    if not working_dir:
        cwd_path = str(root_path)
    else:
        wd_path = Path(working_dir)
        cwd_path = str(wd_path) if wd_path.is_absolute() else str(root_path / wd_path)

    # 小修 A: 避免原地修改模块级变量 engine_cmd
    cmd = list(engine_cmd)
    if cmd and cmd[0] == "python":
        cmd[0] = sys.executable

    # 为 Day 31 预留 pir_input 字段
    req_payload = {
        "request_id": str(uuid.uuid4()),
        "query_payload": query_payload,
        "pir_input": query_payload,  # Day 31 的映射预留点
        "engine_request_type": "standard_query"
    }
    input_json_bytes = json.dumps(req_payload).encode('utf-8')

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd_path
        )
    except FileNotFoundError:
        raise EngineNotFoundError(f"Cannot find engine executable: {cmd[0]} (cwd: {cwd_path})")

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=input_json_bytes),
            timeout=timeout_sec
        )
    except asyncio.TimeoutError:
        try:
            process.kill()
        except:
            pass
        raise EngineTimeoutError(f"Engine execution timed out after {timeout_sec}s")

    if process.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='ignore').strip()
        raise EngineProcessError(f"Exit code {process.returncode}. Stderr: {err_msg}")

    stdout_str = stdout.decode('utf-8', errors='ignore').strip()
    try:
        resp_data = json.loads(stdout_str)
    except json.JSONDecodeError:
        raise EngineProtocolError(f"Engine output is not valid JSON. Raw: {stdout_str[:100]}...")

    engine_meta = resp_data.get("engine_meta", {})

    if resp_data.get("status") != "success":
        err_msg = resp_data.get("error_message", "Unknown engine error")
        raise EngineResponseError(f"Engine logic error: {err_msg} | Meta: {engine_meta}")

    # 小修 C: 返回 tuple，以便上层能利用 engine_meta
    return resp_data.get("result", ""), engine_meta