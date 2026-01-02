import os
import subprocess
import re
import datetime
from dateutil.parser import parse
import argparse
import sys
import shutil
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS

# ========================
# 元数据提取核心功能
# ========================

def extract_exif(file_path):
    """提取图片文件的EXIF元数据"""
    try:
        img = Image.open(file_path)
        exif_data = img._getexif()
        
        if not exif_data:
            return {}
        
        metadata = {
            'date': None,
            'camera': 'UnknownCamera',
            'lens': 'UnknownLens'
        }
        
        # 提取日期时间
        datetime_tag = 36867  # DateTimeOriginal
        if datetime_tag in exif_data:
            try:
                dt_str = exif_data[datetime_tag]
                dt = datetime.datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                metadata['date'] = dt.strftime('%Y%m%d%H%M%S')
            except Exception:
                pass
        
        # 提取相机信息
        make_tag = 271  # Make
        model_tag = 272  # Model
        camera_make = exif_data.get(make_tag, "")
        camera_model = exif_data.get(model_tag, "")
        
        if camera_make and camera_model:
            metadata['camera'] = f"{camera_make.strip()}_{camera_model.strip()}"
        elif camera_model:
            metadata['camera'] = camera_model.strip()
        
        # 提取镜头信息
        lens_tag = 42036  # LensModel (常见于尼康、佳能)
        lens_spec = exif_data.get(lens_tag, "")
        if lens_spec:
            metadata['lens'] = lens_spec.strip()
        else:
            # 尝试其他可能的镜头信息标签
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if "lens" in tag.lower() and isinstance(value, str):
                    metadata['lens'] = value.strip()
                    break
        
        # 清理特殊字符
        metadata['camera'] = re.sub(r'[\\/:*?"<>|]', '', metadata['camera'])[:30]
        metadata['lens'] = re.sub(r'[\\/:*?"<>|]', '', metadata['lens'])[:30]
        
        return metadata
    except Exception as e:
        print(f"EXIF提取错误: {file_path} - {str(e)}")
        return {}

def get_video_metadata(file_path):
    """提取视频文件的元数据"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format_tags=creation_time : stream_tags=creation_time',
        '-show_entries', 'format_tags=make : stream_tags=make',
        '-show_entries', 'format_tags=model : stream_tags=model',
        '-show_entries', 'format_tags=artist',
        '-show_entries', 'format_tags=com.gopro.manufacturer',
        '-show_entries', 'format_tags=com.dji.manufacturer',
        '-of', 'default=noprint_wrappers=1',
        file_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout
        
        metadata = {
            'date': None,
            'camera': 'UnknownCamera',
            'lens': 'UnknownLens'
        }
        
        # 提取日期时间
        date_match = re.search(r'creation_time=([\dT:\-]+)', output)
        if date_match:
            try:
                dt = parse(date_match.group(1))
                metadata['date'] = dt.strftime('%Y%m%d%H%M%S')
            except:
                pass
        
        # 提取相机信息（优先考虑特定设备）
        # 检查GoPro
        gopro_match = re.search(r'com\.gopro\.manufacturer=([^\n]+)', output)
        if gopro_match:
            metadata['camera'] = f"GoPro_{gopro_match.group(1).strip()}"
        else:
            # 检查DJI
            dji_match = re.search(r'com\.dji\.manufacturer=([^\n]+)', output)
            if dji_match:
                metadata['camera'] = f"DJI_{dji_match.group(1).strip()}"
            else:
                # 通用相机信息提取
                make_match = re.search(r'\bmake=([^\n]+)', output, re.IGNORECASE)
                model_match = re.search(r'\bmodel=([^\n]+)', output, re.IGNORECASE)
                
                if make_match and model_match:
                    make = make_match.group(1).strip()
                    model = model_match.group(1).strip()
                    metadata['camera'] = f"{make}_{model}" if make.lower() not in model.lower() else model
                elif model_match:
                    metadata['camera'] = model_match.group(1).strip()
        
        # 尝试提取镜头信息
        artist_match = re.search(r'\bartist=([^\n]+)', output)
        if artist_match:
            artist = artist_match.group(1).strip()
            if 'lens' in artist.lower() or 'focal' in artist.lower():
                metadata['lens'] = artist
        
        # 清理特殊字符
        metadata['camera'] = re.sub(r'[\\/:*?"<>|]', '', metadata['camera'])[:30]
        metadata['lens'] = re.sub(r'[\\/:*?"<>|]', '', metadata['lens'])[:30]
        
        return metadata
    except Exception as e:
        print(f"视频元数据提取错误: {file_path} - {str(e)}")
        return {}

def get_metadata(file_path):
    """智能获取文件的元数据（图片或视频）"""
    ext = os.path.splitext(file_path)[1].lower()
    
    # 图片文件处理
    if ext in {'.jpg', '.jpeg', '.png', '.nef', '.cr2', '.arw', '.dng', '.tiff', '.heic', '.raf'}:
        return extract_exif(file_path)
    
    # 视频文件处理
    elif ext in {'.mp4','.mov','.avi','.mts','.m2ts','.mkv','.flv','.wmv','.mpg','.mpeg','.m4v','.3gp','.vob','.ts','.webm','.hevc','.264','.265'}:
        return get_video_metadata(file_path)
    
    # 其他文件类型
    return {}

# ========================
# 文件处理核心功能
# ========================

def rename_media_files(directory, test_mode=False, custom_template=None):
    """批量重命名目录中的媒体文件"""
    media_extensions = {
        # 视频格式
        '.mp4', '.mov', '.avi', '.mts', '.m2ts', '.mkv', '.flv', '.wmv', '.mpg', '.mpeg',
        '.m4v', '.3gp', '.vob', '.ts', '.webm', '.hevc', '.264', '.265',
        # 图片格式
        '.jpg', '.jpeg', '.png', '.nef', '.cr2', '.arw', '.dng', '.tiff', '.heic', '.raf'
    }
    
    log = []
    naming_counter = {}
    summary = {
        'total': 0,
        'renamed': 0,
        'errors': 0,
        'no_meta': 0,
        'skipped': 0
    }
    
    print(f"🔍 扫描媒体目录: {directory}")
    print(f"📁 检测到 {len(os.listdir(directory))} 个文件...")
    
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        
        if not os.path.isfile(file_path):
            continue
        
        name, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        
        if ext_lower not in media_extensions:
            summary['skipped'] += 1
            continue
        
        summary['total'] += 1
        file_type = "视频" if ext_lower in {'.mp4','.mov','.avi','.mts','.m2ts'} else "图片"
        
        try:
            # 获取元数据
            metadata = get_metadata(file_path)
            
            # 构建新文件名
            date_part = metadata.get('date')
            if not date_part:
                # 使用文件修改时间作为后备方案
                mod_time = os.path.getmtime(file_path)
                date_part = datetime.datetime.fromtimestamp(mod_time).strftime('%Y%m%d%H%M%S')
                summary['no_meta'] += 1
            
            camera_part = metadata.get('camera', 'UnknownCamera')
            lens_part = metadata.get('lens', 'UnknownLens')
            
            # 使用自定义命名模板（如果提供）
            if custom_template:
                base_name = custom_template.format(
                    date=date_part,
                    camera=camera_part,
                    lens=lens_part,
                    ext=ext_lower[1:],  # 不带点的扩展名
                    index=summary['total']
                )
            else:
                base_name = f"{date_part}_{camera_part}_{lens_part}"
            
            # 处理重名冲突
            if base_name in naming_counter:
                naming_counter[base_name] += 1
                new_filename = f"{base_name}_{naming_counter[base_name]}{ext_lower}"
            else:
                naming_counter[base_name] = 0
                new_filename = f"{base_name}{ext_lower}"
            
            new_path = os.path.join(directory, new_filename)
            
            # 测试模式只显示不执行
            if test_mode:
                log.append(f"🔹 TEST: {filename} → {new_filename}")
            else:
                # 执行重命名
                os.rename(file_path, new_path)
                log.append(f"✅ RENAMED: {filename} → {new_filename}")
                summary['renamed'] += 1
            
        except Exception as e:
            error_msg = f"❌ ERROR: {filename} - {str(e)}"
            log.append(error_msg)
            summary['errors'] += 1
            print(error_msg)
    
    # 生成日志报告
    report = f"\n📊 处理报告: {directory}\n"
    report += f"├─ 总共文件: {summary['total']}\n"
    report += f"├─ 成功重命名: {summary['renamed']}\n"
    report += f"├─ 缺少元数据: {summary['no_meta']}\n"
    report += f"├─ 错误文件: {summary['errors']}\n"
    report += f"└─ 跳过文件: {summary['skipped']}\n"
    
    # 保存日志文件
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"renamer_log_{timestamp}.txt"
    log_path = os.path.join(directory, log_filename)
    
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(report + "\n")
        f.write("# 详细处理日志:\n")
        f.write("\n".join(log))
    
    # 返回结果
    print(report)
    print(f"📝 详细日志已保存到: {log_path}")
    
    return summary, log

# ========================
# 依赖管理
# ========================

def check_ffmpeg_installed():
    """检查FFmpeg是否安装"""
    try:
        subprocess.run(['ffprobe', '-version'], 
                       stdout=subprocess.DEVNULL, 
                       stderr=subprocess.DEVNULL)
        return True
    except (FileNotFoundError, OSError):
        return False

def install_ffmpeg():
    """指导用户安装FFmpeg"""
    print("\n⚠️ 需要安装FFmpeg来处理视频元数据")
    print("请选择您的操作系统：")
    print("1. Windows")
    print("2. macOS (使用Homebrew)")
    print("3. Linux (Debian/Ubuntu)")
    print("4. 其他Linux")
    
    choice = input("请输入数字选项: ").strip()
    
    install_cmds = {
        '1': "下载地址: https://www.gyan.dev/ffmpeg/builds/ 下载完整版并添加bin目录到系统PATH",
        '2': "brew install ffmpeg",
        '3': "sudo apt install ffmpeg",
        '4': "请参考官方文档: https://ffmpeg.org/download.html"
    }
    
    cmd = install_cmds.get(choice, "无效选项，请手动安装FFmpeg")
    print(f"\n安装方法: {cmd}")
    print("安装完成后重新运行此程序")
    return False

def check_pillow_installed():
    """检查Pillow是否安装"""
    try:
        import PIL
        return True
    except ImportError:
        return False

def install_dependencies():
    """安装必要的Python依赖"""
    dependencies = []
    
    # 检查FFmpeg
    if not check_ffmpeg_installed():
        print("❌ FFmpeg未安装，视频处理功能将受限")
        print("是否安装FFmpeg？(y/n)")
        if input().lower() == 'y':
            if not install_ffmpeg():
                return False
    
    # 检查Pillow
    if not check_pillow_installed():
        print("❌ Pillow库未安装，图片EXIF处理需要")
        print("是否安装Pillow？(y/n)")
        if input().lower() == 'y':
            dependencies.append('pillow')
    
    # 检查python-dateutil
    try:
        import dateutil
    except ImportError:
        dependencies.append('python-dateutil')
    
    # 安装缺失的依赖
    if dependencies:
        print(f"正在安装依赖: {', '.join(dependencies)}")
        os.system(f"pip install {' '.join(dependencies)}")
    
    return True

# ========================
# 主程序入口
# ========================

def main():
    parser = argparse.ArgumentParser(description='媒体文件元数据批量重命名工具')
    parser.add_argument('directory', nargs='?', default=os.getcwd(), 
                        help='要处理的目录（默认为当前目录）')
    parser.add_argument('--test', action='store_true', 
                        help='测试模式（只显示重命名预览而不实际修改）')
    parser.add_argument('--template', type=str, 
                        help='自定义文件名模板（使用{date}, {camera}, {lens}, {ext}, {index}变量）')
    args = parser.parse_args()
    
    # 检查依赖
    if not install_dependencies():
        print("❌ 依赖检查失败，请手动安装必要组件")
        return
    
    # 检查目录是否存在
    if not os.path.exists(args.directory):
        print(f"❌ 目录不存在: {args.directory}")
        return
    
    # 打印启动信息
    print("\n" + "="*50)
    print(f"📂 媒体文件元数据重命名工具 v1.3")
    print(f"📁 工作目录: {args.directory}")
    print("="*50 + "\n")
    
    if args.test:
        print("⚠️ 测试模式 - 不会实际修改文件")
    
    # 执行重命名
    rename_media_files(args.directory, args.test, args.template)
    
    print("\n✅ 处理完成！")

if __name__ == "__main__":
    main()