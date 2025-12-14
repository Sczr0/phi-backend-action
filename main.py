import os
import sys
import subprocess
import shutil
import time

def flush_print(msg):
    """强制刷新打印，确保GitHub Actions日志实时显示"""
    print(msg, flush=True)

def run_command_stream(command, cwd=None, env=None):
    """
    执行命令并实时打印输出（流式），而不是等运行完再一次性打印。
    这对解包这种耗时操作非常重要，防止GitHub Actions因无输出而超时。
    """
    try:
        # Popen 允许我们实时获取 stdout
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # 将错误也重定向到标准输出，方便一起看
            shell=False,
            text=True,
            encoding='utf-8',
            errors='replace', # 防止编码错误导致脚本崩溃
            cwd=cwd,
            env=env
        )

        # 逐行读取输出
        for line in process.stdout:
            sys.stdout.write(line)
            # sys.stdout.flush() # 通常不需要每行都flush，但如果日志卡顿可以取消注释

        process.wait() # 等待子进程结束

        if process.returncode != 0:
            flush_print(f"\n!! 命令执行失败，返回码: {process.returncode}")
            return False
        return True

    except Exception as e:
        flush_print(f"\n!! 执行命令时发生异常: {e}")
        return False

def download_with_aria2(url, filename, max_retries=3):
    """
    使用 aria2c 多线程下载，抗网络波动能力比 requests 强 N 倍
    """
    flush_print(f"--- 启动 Aria2 下载: {filename} ---")
    
    # 检查 aria2c 是否存在
    if not shutil.which("aria2c"):
        flush_print("错误: 未找到 aria2c。请在 workflow 中运行 'sudo apt-get install -y aria2'")
        sys.exit(1)

    # Aria2 参数详解：
    # -x 16: 16个连接数 (对于跨国大文件至关重要)
    # -s 16: 连接到16个服务器
    # -k 1M: 最小分块大小
    # --max-tries: 内部重试次数
    # --retry-wait: 重试等待时间
    # --user-agent: 伪装UA防止被拦截
    cmd = [
        "aria2c",
        "-x", "16", 
        "-s", "16",
        "-k", "1M",
        "--max-tries=5", 
        "--retry-wait=3",
        "--connect-timeout=60",
        "--user-agent=Mozilla/5.0",
        "-o", filename,
        url
    ]

    # 外层重试逻辑（防止 aria2 彻底挂掉）
    for attempt in range(1, max_retries + 1):
        flush_print(f"尝试下载 (第 {attempt}/{max_retries} 次)...")
        if run_command_stream(cmd):
            flush_print(f"下载成功: {filename}")
            
            # 简单验证文件是否存在且不为空
            if os.path.exists(filename) and os.path.getsize(filename) > 1024:
                return True
            else:
                flush_print("警告: 下载显示成功但文件似乎有问题。")
        
        flush_print(f"警告: 第 {attempt} 次下载失败，等待 5 秒后重试...")
        time.sleep(5)
        
        # 失败后最好删除可能损坏的半成品文件，让 aria2 重新通过断点续传检查（如果有 .aria2 文件）
        # 这里不删 filename，因为 aria2 支持断点续传，保留它更好

    return False

def run_python_script(script_name, arg):
    """运行现有的解包脚本"""
    flush_print(f"\n>>> 开始运行子脚本: {script_name} <<<")
    
    cmd = [sys.executable, script_name, arg]
    success = run_command_stream(cmd)
    
    if not success:
        flush_print(f"!! 致命错误: 脚本 {script_name} 执行失败！")
        sys.exit(1) # 子脚本失败，直接终止
    else:
        flush_print(f">>> 脚本 {script_name} 执行完毕 <<<")

if __name__ == "__main__":
    # 强制让 print 立即输出，防止 buffering
    sys.stdout.reconfigure(line_buffering=True)

    apk_url = os.environ.get('APK_DOWNLOAD_URL')
    if not apk_url:
        flush_print("错误：环境变量 APK_DOWNLOAD_URL 未设置！")
        sys.exit(1)

    apk_filename = "phigros_latest.apk"

    # 1. 使用 Aria2 下载 (核心优化点)
    if not download_with_aria2(apk_url, apk_filename):
        flush_print("!! 最终下载失败，程序退出。")
        sys.exit(1)

    # 2. 依次运行解包脚本
    # 检查脚本是否存在
    if not os.path.exists("gameInformation.py") or not os.path.exists("resource.py"):
        flush_print("错误: 找不到解包脚本 (gameInformation.py 或 resource.py)")
        sys.exit(1)

    run_python_script("gameInformation.py", apk_filename)
    run_python_script("resource.py", apk_filename)

    flush_print("\n=== 所有任务圆满完成！===")