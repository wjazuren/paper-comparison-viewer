# \#Paper Comparison Viewer - 论文对比图查看工具

#  [![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/) [![Qt Version](https://img.shields.io/badge/PyQt-6.x-green)](https://www.riverbankcomputing.com/software/pyqt/) [![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE) 

一款专为超分辨、图像恢复、图像增强等计算机视觉领域学术研究打造的论文对比图查看工具，支持图片批量加载、精准区域选择、放大镜细节查看、自定义裁剪与高质量保存，大幅提升论文对比实验的效率。

 ## ✨ 核心功能 ###

 🖼️ 图片查看与操作 -

**批量加载**：支持 PNG/JPG/BMP/TIFF/WebP 等主流图片格式，自动扫描并加载指定文件夹下的所有图片 - 

**自由缩放平移**：滚轮缩放（0.1x~50x）、右键拖拽平移，双击一键还原自适应显示 - 

**精准区域选择**：  自由画框：手动拖拽选择任意对比区域  - 固定尺寸画框：一键生成 101x51 标准对比框（可自定义尺寸）  - 裁剪中心选取：可视化选取 392x311 裁剪区域中心，批量裁剪所有图片 

### 🔍 细节放大查看 -

 **同步放大镜**：300x300 放大镜窗口，支持 1x~20x 放大倍数 

 **十字线定位**：红色虚线十字线，精准定位像素级细节 

**实时坐标显示**：显示原图坐标与缩放比例，便于精准对比 

### 💾 高质量保存

- **多格式导出**：支持 PNG/JPEG/TIFF/BMP/WebP/PDF 格式保存

- **自定义参数**：可设置保存质量（1-100%）、DPI（72-1200）

- 灵活保存方式

  ：

  - 保存全部图片（支持添加外边框）
  - 保存选中区域（可保留红边框）
  - 分别保存每张图片 / 区域
  - 保存当前视图（含缩放 / 平移状态）

### 🎨 人性化设计

- **深色主题**：护眼深色界面，适合长时间学术研究
- **快捷键支持**：Ctrl+O/Ctrl+S 等常用操作快捷键
- **状态提示**：实时显示操作状态与图片信息
- **表格列表**：图片文件名、尺寸一目了然，便于管理

## 📋 环境要求

### 系统要求

- Windows/Linux/macOS（推荐 Windows 10/11 或 Ubuntu 20.04+）

### 依赖包

bash运行

```
# 核心依赖
Python >= 3.8
PyQt6 >= 6.4.0
Pillow >= 9.0.0
numpy >= 1.21.0
```

## 🚀 快速开始

### 1. 环境安装

bash运行

```
# 克隆仓库
git clone https://github.com/wjazuren/paper-comparison-viewer.git
cd paper-comparison-viewer

# 创建虚拟环境（可选但推荐）
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 创建 requirements.txt

txt

```
PyQt6>=6.4.0
Pillow>=9.0.0
numpy>=1.21.0
```

### 3. 运行程序

bash

运行

```
python paper_comparison_viewer.py
```

## 📖 使用指南

### 基础操作

1. **打开文件夹**：点击「📁 打开文件夹」或按 Ctrl+O，选择包含对比图片的文件夹

2. **查看图片**：滚轮缩放图片，右键拖拽平移，双击还原自适应显示

3. 选择对比区域

   ：

   - 自由画框：点击「⬚ 自由画框」，在图片上拖拽选择区域
   - 固定画框：点击「📌 固定画框 (101x51)」，移动鼠标预览后点击确定

4. **裁剪图片**：点击「🎯 选取裁剪区域」，在图片上选择中心点，自动裁剪为 392x311

5. **保存结果**：根据需求选择「保存全部」「保存区域」「分别保存」等选项

### 放大镜设置

- 调整「放大倍数」滑块可改变放大比例（1x~20x）
- 勾选 / 取消「同步所有图片放大镜」可切换同步模式
- 勾选 / 取消「显示十字线」可控制十字线显示

### 保存设置

- 选择保存格式：PNG（无损）/JPEG（高压缩）/TIFF（专业）等
- 调整质量：JPEG/WebP 格式建议 90-95%
- 调整 DPI：论文投稿建议 300 DPI
- 边框选项：可选择是否为原图添加外边框，或为局部区域保留红边框

## ⌨️ 快捷键

| 快捷键 |      功能      |
| :----: | :------------: |
| Ctrl+O |   打开文件夹   |
| Ctrl+R |    刷新图片    |
| Ctrl+S |  保存全部图片  |
| Ctrl+Q |    退出程序    |
|   +    | 增大放大镜倍数 |
|   -    | 减小放大镜倍数 |
|  Esc   |  清除选中区域  |

## 🎯 适用场景

- 超分辨（Super-Resolution）论文对比图查看
- 图像恢复（Image Restoration）实验结果对比
- 图像增强（Image Enhancement）效果分析
- 去模糊 / 去噪 / 去雨等视觉任务的结果对比
- 论文投稿前的对比图裁剪与保存

## 🔧 自定义修改

- 修改固定画框尺寸：修改 `toggle_fixed_region` 方法中的 `target_w, target_h = 101, 51`
- 修改裁剪尺寸：修改 `ImageLoaderThread` 中的 `target_w, target_h = 392, 311`
- 调整界面样式：修改 `ComparisonViewer.__init__` 中的 CSS 样式表
- 添加新格式支持：扩展 `fmt_combo` 下拉框选项及保存逻辑



## 🙏 致谢

- [PyQt6](https://link.wtturl.cn/?target=https%3A%2F%2Fwww.riverbankcomputing.com%2Fsoftware%2Fpyqt%2F&scene=im&aid=497858&lang=zh) - 强大的 Python GUI 框架
- [Pillow](https://link.wtturl.cn/?target=https%3A%2F%2Fpython-pillow.org%2F&scene=im&aid=497858&lang=zh) - 专业的图像处理库
- 所有为计算机视觉学术研究做出贡献的研究者

## 📞 问题反馈

如有任何问题或建议，欢迎提交 Issue 或 Pull Request，我们会尽快回复！