使用说明

1. **安装依赖**：
   ```bash
   pip install exifread
   ```

2. **修改路径**：
   将脚本中的 `PHOTO_DIR` 改为你的照片目录路径
   ```python
   PHOTO_DIR = r"C:\Your\Photos\Directory"  # Windows路径示例
   # 或
   PHOTO_DIR = "/path/to/your/photos"  # Linux/Mac路径示例
   ```

3. **运行脚本**：
   ```bash
   python rename_photos.py
   ```

### 功能特点

1. **智能EXIF提取**：
   - 支持多重日期源获取（优先使用原始拍摄时间）
   - 自动组合相机制造商和型号（如 `SONY_ILCE-7M4`）
   - 镜头型号多标签探测（支持主流品牌特殊标签）

2. **特殊机型适配**：
   - 自动修复富士相机镜头命名格式（添加 `Fujinon_` 前缀）
   - 处理尼康/佳能RAW格式文件（.NEF/.CR2）

3. **安全机制**：
   - 自动过滤文件名非法字符（`\/:*?"<>|`）
   - 重名文件自动添加序号（`20240515-SONY_ILCE7M4-SEL2470GM2_1.jpg`）
   - 详细操作日志记录（保存为 `rename_log.txt`）

4. **支持格式**：
   ```python
   ['.jpg', '.jpeg', '.nef', '.cr2', '.arw', '.dng', '.tiff']
   ```

### 输出示例
```
20240515-SONY_ILCE7M4-SEL2470GM2.jpg
20240516-CANON_EOSR5-RF70200F28L.jpg
20240517-FUJIFILM_XT5-Fujinon_XF35mmF14.jpg
```

### 注意事项
1. 原始文件不会被删除，只是重命名
2. 无EXIF数据的文件会标记为：
   - `NoDate-CameraModel-LensModel.jpg`
3. 处理前建议备份原始文件
4. 支持常见品牌相机（索尼/佳能/尼康/富士/松下等）

如果需要处理视频文件或更复杂的EXIF场景，可以扩展此脚本添加相应功能。
