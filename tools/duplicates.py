# 文件路径
file_path = "../store.txt"


# 直接修改原文件并输出被删掉的内容
def remove_duplicates_in_place(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # 去重逻辑，保持顺序
    seen = set()
    unique_lines = []
    removed_lines = []

    for line in lines:
        stripped_line = line.strip()
        if stripped_line and stripped_line not in seen:
            unique_lines.append(stripped_line)
            seen.add(stripped_line)
        elif stripped_line:
            removed_lines.append(stripped_line)

    # 写入去重后的内容到原文件
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write("\n".join(unique_lines) + "\n")

    # 输出被删掉的内容
    if removed_lines:
        print("以下句子被删除（重复项）：")
        for line in removed_lines:
            print(line)
    else:
        print("没有重复的句子被删除。")

    print(f"去重完成，原文件已更新: {file_path}")


# 调用函数
remove_duplicates_in_place(file_path)
