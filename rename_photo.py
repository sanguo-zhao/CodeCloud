import os
import subprocess
import re
import datetime
import argparse
import zipfile
import tempfile

from dateutil.parser import parse
from PIL import Image
from PIL.ExifTags import TAGS

# ========================
# EXIF / 元数据提取
# ========================

def extract_exif(file_path):
    try:
        img = Image.open(file_path)
        exif = img._getexif()
        if not exif:
            return {}

        meta = {
            'date': None,
            'camera': 'UnknownCamera',
            'lens': 'UnknownLens'
        }

        # Date
        if 36867 in exif:
            try:
                dt = datetime.datetime.strptime(
                    exif[36867], "%Y:%m:%d %H:%M:%S"
                )
                meta['date'] = dt.strftime('%Y%m%d%H%M%S')
            except:
                pass

        # Camera
        make = exif.get(271, "")
        model = exif.get(272, "")
        if make and model:
            meta['camera'] = f"{make.strip()}_{model.strip()}"
        elif model:
            meta['camera'] = model.strip()

        # Lens
        lens = exif.get(42036, "")
        if lens:
            meta['lens'] = lens.strip()
        else:
            for k, v in exif.items():
                tag = TAGS.get(k, "").lower()
                if "lens" in tag and isinstance(v, str):
                    meta['lens'] = v.strip()
                    break

        meta['camera'] = re.sub(r'[\\/:*?"<>|]', '', meta['camera'])[:40]
        meta['lens'] = re.sub(r'[\\/:*?"<>|]', '', meta['lens'])[:40]

        return meta
    except:
        return {}

def get_video_metadata(file_path):
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format_tags=creation_time,make,model',
        '-of', 'default=noprint_wrappers=1',
        file_path
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        out = r.stdout

        meta = {
            'date': None,
            'camera': 'UnknownCamera',
            'lens': 'UnknownLens'
        }

        m = re.search(r'creation_time=([^\n]+)', out)
        if m:
            try:
                dt = parse(m.group(1))
                meta['date'] = dt.strftime('%Y%m%d%H%M%S')
            except:
                pass

        make = re.search(r'make=([^\n]+)', out)
        model = re.search(r'model=([^\n]+)', out)
        if make and model:
            meta['camera'] = f"{make.group(1)}_{model.group(1)}"
        elif model:
            meta['camera'] = model.group(1)

        meta['camera'] = re.sub(r'[\\/:*?"<>|]', '', meta['camera'])[:40]
        return meta
    except:
        return {}

def extract_livp_metadata(file_path):
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(file_path, 'r') as z:
                z.extractall(tmp)

            for root, _, files in os.walk(tmp):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in {'.jpg', '.jpeg', '.heic'}:
                        p = os.path.join(root, f)
                        meta = extract_exif(p)
                        if meta.get('date'):
                            return meta
                        if ext == '.heic':
                            meta = get_video_metadata(p)
                            if meta.get('date'):
                                return meta
        return {}
    except:
        return {}

def get_metadata(file_path):
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.livp':
        return extract_livp_metadata(file_path)

    if ext in {'.jpg','.jpeg','.png','.nef','.cr2','.arw','.dng','.tiff','.raf'}:
        return extract_exif(file_path)

    if ext == '.heic':
        meta = extract_exif(file_path)
        return meta if meta.get('date') else get_video_metadata(file_path)

    if ext in {
        '.mp4','.mov','.avi','.mts','.m2ts','.mkv',
        '.flv','.wmv','.mpg','.mpeg','.m4v','.3gp',
        '.vob','.ts','.webm'
    }:
        return get_video_metadata(file_path)

    return {}

# ========================
# 重命名核心（已修复 WinError 183）
# ========================

def rename_media_files(directory, test=False, template=None):
    media_exts = {
        '.jpg','.jpeg','.png','.nef','.cr2','.arw','.dng',
        '.tiff','.raf','.heic','.livp',
        '.mp4','.mov','.avi','.mts','.m2ts','.mkv',
        '.flv','.wmv','.mpg','.mpeg','.m4v','.3gp',
        '.vob','.ts','.webm'
    }

    total = renamed = no_meta = 0

    for fn in os.listdir(directory):
        src = os.path.join(directory, fn)
        if not os.path.isfile(src):
            continue

        name, ext = os.path.splitext(fn)
        ext = ext.lower()
        if ext not in media_exts:
            continue

        total += 1
        meta = get_metadata(src)

        date = meta.get('date')
        if not date:
            date = datetime.datetime.fromtimestamp(
                os.path.getmtime(src)
            ).strftime('%Y%m%d%H%M%S')
            no_meta += 1

        camera = meta.get('camera', 'UnknownCamera')
        lens = meta.get('lens', 'UnknownLens')

        base = (
            template.format(
                date=date, camera=camera,
                lens=lens, ext=ext[1:], index=total
            )
            if template else f"{date}_{camera}_{lens}"
        )

        # ✅ 关键修复：真实文件存在判断
        idx = 0
        while True:
            new_name = f"{base}{ext}" if idx == 0 else f"{base}_{idx}{ext}"
            dst = os.path.join(directory, new_name)
            if not os.path.exists(dst):
                break
            idx += 1

        if test:
            print(f"TEST: {fn} → {new_name}")
        else:
            os.rename(src, dst)
            renamed += 1
            print(f"RENAMED: {fn} → {new_name}")

    print("\n处理完成")
    print(f"总文件: {total}")
    print(f"已重命名: {renamed}")
    print(f"无元数据: {no_meta}")

# ========================
# 主入口
# ========================

def main():
    parser = argparse.ArgumentParser("媒体文件批量重命名（支持 LIVP / HEIC）")
    parser.add_argument('directory', nargs='?', default=os.getcwd())
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--template', type=str)
    args = parser.parse_args()

    rename_media_files(args.directory, args.test, args.template)

if __name__ == "__main__":
    main()
