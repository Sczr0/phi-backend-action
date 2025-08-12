import json
import os
import sys
from UnityPy import Environment
import zipfile
import subprocess # 为了兼容性，提前导入

# DEBUG 开关，当前未使用
DEBUG = False

def run(path):
    """
    从 Phigros 的 APK 文件中提取游戏数据并保存为结构化文件。
    """
    # 1. 加载 TypeTree 定义，用于解析 Unity 自定义对象
    try:
        with open("typetree.json", "r", encoding="utf8") as f:
            typetree = json.load(f)
    except FileNotFoundError:
        print("错误: 找不到 typetree.json 文件。请确保该文件与脚本在同一目录下。")
        sys.exit(1)

    # 2. 初始化 UnityPy 环境并加载游戏资源文件
    env = Environment()
    try:
        with zipfile.ZipFile(path) as apk:
            # globalgamemanagers.assets 通常包含全局设置和初始数据
            with apk.open("assets/bin/Data/globalgamemanagers.assets") as f:
                env.load_file(f, name="assets/bin/Data/globalgamemanagers.assets")
            # level0 通常是主场景或包含核心逻辑的资源包
            with apk.open("assets/bin/Data/level0") as f:
                env.load_file(f)
    except (zipfile.BadZipFile, FileNotFoundError, KeyError) as e:
        print(f"错误: 无法读取或解析 APK 文件 '{path}'。请确保路径正确且文件未损坏。")
        print(f"详细信息: {e}")
        sys.exit(1)

    # 3. 遍历 Unity 对象，提取核心数据
    GameInformation = None
    Collections = None
    Tips = None
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            data = obj.read()
            # 通过脚本名称识别不同的数据管理器
            script_name = data.m_Script.get_obj().read().name
            if script_name == "GameInformation":
                GameInformation = obj.read_typetree(typetree["GameInformation"])
            elif script_name == "GetCollectionControl":
                Collections = obj.read_typetree(typetree["GetCollectionControl"], True)
            elif script_name == "TipsProvider":
                Tips = obj.read_typetree(typetree["TipsProvider"], True)
    
    # 检查是否成功提取了所有需要的数据
    if not all([GameInformation, Collections, Tips]):
        print("警告: 未能从资源文件中完整提取 GameInformation, GetCollectionControl 或 TipsProvider。输出可能不完整。")
        return

    # 4. 处理歌曲信息 (GameInformation)
    difficulty = []
    table = []
    for key, songs in GameInformation["song"].items():
        if key == "otherSongs":
            continue
        for song in songs:
            # 数据清洗：移除多余的难度和谱师信息
            if len(song["difficulty"]) == 5:
                song["difficulty"].pop()
            if song["difficulty"] and song["difficulty"][-1] == 0.0:
                song["difficulty"].pop()
                song["charter"].pop()
            
            # 准备难度数据
            difficulty_values = [str(round(d, 1)) for d in song["difficulty"]]
            
            # 准备歌曲ID，并移除可能的后缀
            song_id = song["songsId"][:-2]
            
            # 添加到 difficulty 列表
            difficulty.append([song_id, *difficulty_values])
            
            # 添加到 table 列表 (ID, 歌名, 作曲, 插画, 谱师们)
            table.append([
                song_id,
                song["songsName"],
                song["composer"],
                song["illustrator"],
                *song["charter"]
            ])

    # 5. 将处理好的数据写入文件
    
    # 写入 difficulty.csv
    with open("info/difficulty.csv", "w", encoding="utf8", newline='') as f:
        f.write("id,EZ,HD,IN,AT\n")
        for item in difficulty:
            row = list(item)
            while len(row) < 5: # 补齐到 ID + 4个难度
                row.append("")
            f.write(",".join(map(str, row[:5])))
            f.write("\n")

    # 写入 info.csv (动态处理谱师列)
    with open("info/info.csv", "w", encoding="utf8", newline='') as f:
        max_columns = max(len(row) for row in table) if table else 4
        
        headers = ["id", "song", "composer", "illustrator"]
        num_charters = max_columns - len(headers)
        for i in range(1, num_charters + 1):
            headers.append(f"charter{i}")
        
        f.write(",".join(headers) + "\n")
        
        for item in table:
            padded_item = list(item)
            while len(padded_item) < len(headers):
                padded_item.append("")
            
            formatted_item = []
            for field in padded_item:
                if isinstance(field, str) and "," in field:
                    formatted_item.append(f'"{field}"')
                else:
                    formatted_item.append(str(field))
            
            f.write(",".join(formatted_item))
            f.write("\n")

    # 6. 处理单曲封面和插画信息
    single = []
    illustration = []
    for key in GameInformation["keyStore"]:
        if key["kindOfKey"] == 0:
            single.append(key["keyName"])
        elif key["kindOfKey"] == 2 and key["keyName"] != "Introduction" and key["keyName"] not in single:
            illustration.append(key["keyName"])

    with open("info/single.txt", "w", encoding="utf8") as f:
        f.write("\n".join(single))
        f.write("\n")

    with open("info/illustration.txt", "w", encoding="utf8") as f:
        f.write("\n".join(illustration))
        f.write("\n")

    # 7. 处理收藏品信息 (Collections)
    D = {}
    for item in Collections.collectionItems:
        if item.key in D:
            D[item.key][1] = item.subIndex
        else:
            D[item.key] = [item.multiLanguageTitle.chinese, item.subIndex]

    with open("info/collection.tsv", "w", encoding="utf8") as f:
        for key, value in D.items():
            f.write(f"{key}\t{value[0]}\t{value[1]}\n")

    # 8. 处理头像信息
    with open("info/avatar.txt", "w", encoding="utf8") as avatar, \
         open("info/tmp.tsv", "w", encoding="utf8") as tmp:
        for item in Collections.avatars:
            avatar.write(f"{item.name}\n")
            tmp.write(f"{item.name}\t{item.addressableKey[7:]}\n")

    # 9. 处理提示语 (Tips)
    with open("info/tips.txt", "w", encoding="utf8") as f:
        if Tips and Tips.tips:
            for tip in Tips.tips[0].tips:
                f.write(f"{tip}\n")

    print("数据提取完成，文件已保存至 'info' 目录。")

if __name__ == "__main__":
    path = ""
    # 自动检测路径 (适用于有 root 的 Android 环境)
    if len(sys.argv) == 1 and sys.platform != "win32" and os.path.isdir("/data/"):
        print("尝试在 Android 环境下自动查找 Phigros APK 路径...")
        try:
            # 使用 shell=True 需要谨慎，但在这里 pm 命令是固定的
            r = subprocess.run("pm path com.PigeonGames.Phigros", 
                               stdin=subprocess.DEVNULL, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               shell=True, 
                               check=True) # check=True 会在命令失败时抛出异常
            # stdout 的格式通常是 'package:/path/to/base.apk\n'
            path = r.stdout.decode().strip().replace("package:", "")
            if not os.path.exists(path):
                 print(f"自动找到的路径 '{path}' 无效，请手动指定。")
                 path = ""
            else:
                 print(f"成功找到 APK: {path}")

        except (subprocess.CalledProcessError, FileNotFoundError):
            print("自动查找失败。请确保您在有 root 的 Android 环境中，或手动提供 APK 路径。")
            
    # 如果自动查找失败或提供了命令行参数，则使用参数
    if not path:
        if len(sys.argv) > 1:
            path = sys.argv[1]
        else:
            print("用法: python your_script_name.py <path_to_apk>")
            sys.exit(1)

    if not os.path.exists(path):
        print(f"错误: 文件或路径不存在 -> '{path}'")
        sys.exit(1)

    # 创建输出目录
    if not os.path.isdir("info"):
        os.mkdir("info")
    
    run(path)