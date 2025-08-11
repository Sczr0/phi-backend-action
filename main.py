import os
import sys
import subprocess
import requests
def download_file(url, filename):
    """使用requests下载文件，只在关键节点打印进度，避免刷屏"""
    print(f"开始下载: {url}")
    print(f"保存到: {filename}")
    try:
        with requests.get(url, stream=True, timeout=300) as r: # 增加5分钟超时
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            if total_size == 0:
                print("警告：无法获取文件大小，无法显示进度。")
            
            downloaded = 0
            # 我们设置一个标记，只在每下载10%时报告一次进度
            progress_marker = 10 

            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        if progress >= progress_marker:
                            print(f"下载进度: {progress:.0f}%")
                            progress_marker += 10 # 下一个报告点是再增加10%
        
        print("下载完成！")

    except requests.exceptions.RequestException as e:
        print(f"\n!! 下载失败: {e}")
        sys.exit(1)
def run_script(script_name, apk_path):
    """运行一个子脚本，并检查是否成功"""
    print(f"\n--- 开始运行脚本: {script_name} ---")
    # 使用subprocess来调用你的脚本，就像在命令行里运行一样
    result = subprocess.run([sys.executable, script_name, apk_path], capture_output=True, text=True, encoding='utf-8')
    
    # 打印脚本的输出，方便调试
    print(result.stdout)
    if result.stderr:
        print("错误输出:")
        print(result.stderr)
        
    if result.returncode != 0:
        print(f"!! 脚本 {script_name} 运行失败! 错误码: {result.returncode}")
        sys.exit(1) # 如果失败，则终止整个流程
    else:
        print(f"--- 脚本 {script_name} 运行成功 ---")


if __name__ == "__main__":
    # 从环境变量中获取Worker传来的下载链接
    apk_url = os.environ.get('APK_DOWNLOAD_URL')

    if not apk_url:
        print("错误：没有在环境变量中找到下载链接 (APK_DOWNLOAD_URL)！")
        sys.exit(1)

    apk_filename = "phigros_latest.apk"
    
    # 1. 下载APK
    download_file(apk_url, apk_filename)

    # 2. 依次运行你的两个核心脚本
    run_script("gameInformation.py", apk_filename)
    run_script("resource.py", apk_filename)

    print("\n所有任务成功完成！")