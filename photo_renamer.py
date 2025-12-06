import os
import exifread
from datetime import datetime
import re
import argparse
import traceback

def sanitize_path(path):
    """规范化路径输入，处理用户复制粘贴的特殊字符"""
    # 移除可能复制进来的引号
    path = re.sub(r'^[\'"](.+)[\'"]$', r'\1', path.strip())
    # 转换Windows路径分隔符
    return os.path.normpath(path)

def validate_directory(path):
    """验证并创建目录（如果不存在）"""
    if not os.path.exists(path):
        print(f"⚠️ 目录不存在: {path}")
        create = input("是否创建此目录？(y/n): ").lower()
        if create == 'y':
            os.makedirs(path)
            print(f"✅ 已创建目录: {path}")
        else:
            raise FileNotFoundError(f"目录不存在: {path}")
    
    if not os.path.isdir(path):
        raise NotADirectoryError(f"路径不是目录: {path}")
    
    return os.path.abspath(path)

def sanitize_filename(text):
    """清理文件名中的非法字符并规范化"""
    # 移除非法字符
    text = re.sub(r'[\\/:*?"<>|]', '_', str(text))
    # 移除首尾空格和点号
    text = text.strip('. ')
    # 替换连续空格为单下划线
    text = re.sub(r'\s+', '_', text)
    # 限制最大长度
    return text[:40]

def extract_exif(file_path):
    """提取EXIF信息并规范化"""
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False, stop_tag='thumbnail')
    except Exception as e:
        raise IOError(f"无法读取文件: {str(e)}")
    
    # 提取拍摄日期（精确到秒）
    date_tags = ['EXIF DateTimeOriginal', 'Image DateTime', 'EXIF DateTimeDigitized']
    date_obj = None
    for tag in date_tags:
        if tag in tags:
            try:
                date_str = str(tags[tag])
                # 处理可能的格式变化
                date_str = re.sub(r'[^\d:]', '', date_str[:19])
                date_obj = datetime.strptime(date_str, '%Y:%m:%d%H:%M:%S')
                break
            except ValueError:
                continue
    
    # 提取相机信息
    make = str(tags.get('Image Make', 'UnknownMake')).strip()
    model = str(tags.get('Image Model', 'UnknownModel')).strip()
    
    # 智能处理相机型号
    camera = model
    if make.lower() not in model.lower() and make != 'UnknownMake':
        camera = f"{make}_{model}"
    
    # 移除相机型号中的冗余信息
    camera = re.sub(r'\bcamera\b|\bdigital\b', '', camera, flags=re.IGNORECASE).strip()
    
    # 提取镜头信息
    lens_tags = ['EXIF LensModel', 'EXIF LensID', 'EXIF LensType', 'EXIF LensSpecification']
    lens = 'UnknownLens'
    for tag in lens_tags:
        if tag in tags:
            lens = str(tags[tag])
            # 简化常见镜头命名
            if 'mm' in lens:
                lens = re.sub(r'^.*?(\d+-\d+mm\b|\d+mm\b)', r'\1', lens)
            break
    
    # 特殊品牌处理
    if 'FUJIFILM' in make.upper() and 'Fujinon' not in lens:
        lens = f"Fujinon_{lens}"
    elif 'SONY' in make.upper() and lens == 'UnknownLens':
        lens = tags.get('MakerNote:LensType', lens)
    
    return date_obj, sanitize_filename(camera), sanitize_filename(lens)

def batch_rename(directory):
    """批量重命名目录中的图片"""
    extensions = ['.jpg', '.jpeg', '.png', '.nef', '.cr2', '.arw', '.dng', '.tiff', '.heic', '.raf']
    log = []
    counter = {}
    
    print(f"🔍 扫描目录: {directory}")
    file_count = 0
    renamed_count = 0
    error_count = 0
    
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        
        # 跳过目录
        if not os.path.isfile(file_path):
            continue
            
        name, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        
        if ext_lower not in extensions:
            continue
            
        file_count += 1
        
        try:
            date_obj, camera, lens = extract_exif(file_path)
            
            # 处理日期格式
            if date_obj:
                timestamp = date_obj.strftime('%Y%m%d%H%M%S')  # 年月日时分秒
            else:
                timestamp = "NoDate"
                log.append(f"⚠️ WARNING: {filename} - 未找到EXIF日期信息")
            
            # 创建基础文件名
            base_name = f"{timestamp}-{camera}-{lens}"
            
            # 处理重复文件名
            if base_name in counter:
                counter[base_name] += 1
                new_filename = f"{base_name}_{counter[base_name]}{ext_lower}"
            else:
                counter[base_name] = 0
                new_filename = f"{base_name}{ext_lower}"
            
            new_path = os.path.join(directory, new_filename)
            
            # 跳过无需重命名的文件
            if file_path == new_path:
                log.append(f"⏩ SKIPPED: {filename} (文件名无需更改)")
                continue
            
            # 执行重命名
            os.rename(file_path, new_path)
            log.append(f"✅ RENAMED: {filename} → {new_filename}")
            renamed_count += 1
            
        except Exception as e:
            error_msg = f"❌ ERROR: {filename} - {str(e)}"
            log.append(error_msg)
            error_count += 1
            print(error_msg)
            # 打印详细错误信息用于调试
            # print(traceback.format_exc())
    
    # 保存日志
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"photo_rename_log_{timestamp}.txt"
    log_file = os.path.join(directory, log_filename)
    
    summary = [
        f"📊 批量重命名结果摘要  📊",
        f"扫描目录: {directory}",
        f"处理文件总数: {file_count}",
        f"成功重命名: {renamed_count}",
        f"跳过文件: {file_count - renamed_count - error_count}",
        f"错误数量: {error_count}",
        f"日志文件: {log_filename}"
    ]
    
    full_log = "\n".join(summary + [""] + log)
    
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(full_log)
            print(f"📝 日志已保存至: {log_file}")
    except Exception as e:
        print(f"❌ 无法保存日志: {str(e)}")
        print("\n".join(summary))
    
    return full_log

def main():
    print("\n📷 图片批量重命名工具 (基于EXIF信息) 📷")
    
    # 创建命令行参数解析
    parser = argparse.ArgumentParser(description='批量重命名图片文件')
    parser.add_argument('directory', type=str, nargs='?', help='包含图片的目录路径')
    
    try:
        args = parser.parse_args()
        
        if args.directory:
            target_dir = sanitize_path(args.directory)
        else:
            # 交互模式
            print("\n请输入包含图片的目录路径（或拖放文件夹到此窗口）:")
            target_dir = sanitize_path(input("> ").strip())
        
        # 验证并规范化路径
        validated_dir = validate_directory(target_dir)
        
        print("\n" + "="*50)
        print(f"📂 目标目录: {validated_dir}")
        print("="*50 + "\n")
        
        # 执行重命名
        log = batch_rename(validated_dir)
        
        # 显示摘要
        print("\n" + "="*50)
        [print(line) for line in log.split('\n') if line.startswith('📊')]
        
    except Exception as e:
        print(f"\n❌ 严重错误: {str(e)}")
        print("建议检查路径是否正确，或使用引号包裹包含空格的路径")
        print("示例: \"C:/My Photos/2024 Summer\"")
        print("或: '/Users/name/My Pictures'")

if __name__ == "__main__":
    main()