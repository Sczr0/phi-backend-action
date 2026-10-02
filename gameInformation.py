import json
import os
import sys
from UnityPy import Environment
import zipfile

DEBUG = False

DATA_PREFIX = "assets/bin/Data/"


def read_data_file(apk, namelist, name):
    # 与 PhiInfo 的 GetDataFile 一致：优先直接条目，其次合并 .split 分片
    path = DATA_PREFIX + name
    if path in namelist:
        return apk.read(path)
    parts = []
    index = 0
    while "%s.split%d" % (path, index) in namelist:
        parts.append(apk.read("%s.split%d" % (path, index)))
        index += 1
    return b"".join(parts) if parts else None


def load_data_files(env, apk):
    # 4.0.1 起 level/sharedassets 等被并入 data.unity3d，更早版本则散落为独立条目。
    # 全部序列化文件都要加载：MonoBehaviour 的 m_Script 可能跨文件引用 MonoScript。
    namelist = set(apk.namelist())
    loaded = set()
    for entry in namelist:
        if not entry.startswith(DATA_PREFIX):
            continue
        name = entry[len(DATA_PREFIX):]
        if "/" in name:
            continue
        if ".split" in name:
            name = name[:name.index(".split")]
        if name in loaded:
            continue
        if not (name.endswith(".assets") or name.endswith(".unity3d") or "." not in name):
            continue
        data = read_data_file(apk, namelist, name)
        if data is None:
            continue
        env.load_file(data, name=DATA_PREFIX + name)
        loaded.add(name)


def run(path):
    with open("typetree.json") as f:
        typetree = json.load(f)
    env = Environment()
    env.path = os.getcwd()
    with zipfile.ZipFile(path) as apk:
        load_data_files(env, apk)
    seen = set()
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        identity = (obj.assets_file.name, obj.path_id)
        if identity in seen:
            continue
        seen.add(identity)
        try:
            data = obj.read()
            script = data.m_Script.get_obj()
            if script is None:
                continue
            script_name = script.read().name
        except Exception:
            continue
        if script_name == "GameInformation":
            GameInformation = obj.read_typetree(typetree["GameInformation"])
        elif script_name == "GetCollectionControl":
            Collections = obj.read_typetree(typetree["GetCollectionControl"], True)
        elif script_name == "TipsProvider":
            Tips = obj.read_typetree(typetree["TipsProvider"], True)

    difficulty = []
    table = []
    for key, songs in GameInformation["song"].items():
        if key == "otherSongs":
            continue
        for song in songs:
            if len(song["difficulty"]) == 5:
                song["difficulty"].pop()
            if song["difficulty"][-1] == 0.0:
                song["difficulty"].pop()
                song["charter"].pop()
            for i in range(len(song["difficulty"])):
                song["difficulty"][i] = str(round(song["difficulty"][i], 1))
            song["songsId"] = song["songsId"][:-2]
            
            # 确保 difficulty 有 4 个元素 (EZ, HD, IN, AT)，不足的用空字符串填充
            diff_item = [song["songsId"]]
            for i in range(4):
                if i < len(song["difficulty"]):
                    diff_item.append(song["difficulty"][i])
                else:
                    diff_item.append("")
            difficulty.append(diff_item)
            
            # 构建 table 数据，格式为：id, song, composer, illustrator, EZ, HD, IN, AT
            table_item = [
                song["songsId"],
                song["songsName"],
                song["composer"],
                song["illustrator"]
            ]
            # 添加难度值
            for i in range(4):
                if i < len(song["difficulty"]):
                    table_item.append(song["difficulty"][i])
                else:
                    table_item.append("")
            table.append(table_item)

    # print(difficulty)
    # print(table)

    with open("info/difficulty.csv", "w", encoding="utf8") as f:
        # 写入 CSV 头部
        f.write("id,EZ,HD,IN,AT\n")
        for item in difficulty:
            f.write(",".join(map(str, item)))
            f.write("\n")

    with open("info/info.csv", "w", encoding="utf8") as f:
        # 写入 CSV 头部
        f.write("id,song,composer,illustrator,EZ,HD,IN,AT\n")
        for item in table:
            # 处理字段中可能包含的逗号，用双引号包裹
            formatted_item = []
            for field in item:
                if isinstance(field, str) and "," in field:
                    formatted_item.append(f'"{field}"')
                else:
                    formatted_item.append(str(field))
            f.write(",".join(formatted_item))
            f.write("\n")

    single = []
    illustration = []
    for key in GameInformation["keyStore"]:
        if key["kindOfKey"] == 0:
            single.append(key["keyName"])
        elif key["kindOfKey"] == 2 and key["keyName"] != "Introduction" and key["keyName"] not in single:
            illustration.append(key["keyName"])

    with open("info/single.txt", "w", encoding="utf8") as f:
        for item in single:
            f.write("%s\n" % item)

    with open("info/illustration.txt", "w", encoding="utf8") as f:
        for item in illustration:
            f.write("%s\n" % item)
    # print(single)
    # print(illustration)

    D = {}
    for item in Collections.collectionItems:
        if item.key in D:
            D[item.key][1] = item.subIndex
        else:
            D[item.key] = [item.multiLanguageTitle.chinese, item.subIndex]

    with open("info/collection.tsv", "w", encoding="utf8") as f:
        for key, value in D.items():
            f.write("%s\t%s\t%s\n" % (key, value[0], value[1]))

    with open("info/avatar.txt", "w", encoding="utf8") as avatar:
        with open("info/tmp.tsv", "w", encoding="utf8") as tmp:
            for item in Collections.avatars:
                avatar.write(item.name)
                avatar.write("\n")
                tmp.write("%s\t%s\n" % (item.name, item.addressableKey[7:]))

    with open("info/tips.txt", "w", encoding="utf8") as f:
        for tip in Tips.tips[0].tips:
            f.write(tip)
            f.write("\n")


if __name__ == "__main__":
    if len(sys.argv) == 1 and os.path.isdir("/data/"):
        import subprocess
        r = subprocess.run("pm path com.PigeonGames.Phigros",stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,shell=True)
        path = r.stdout[8:-1].decode()
    else:
        path = sys.argv[1]
    if not os.path.isdir("info"):
        os.mkdir("info")
    run(path)