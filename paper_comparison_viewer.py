#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论文方法对比图查看工具 (Paper Comparison Viewer)
用于学术论文中方法对比的可视化查看与保存
"""

import sys
import os
import glob
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QFileDialog, QGridLayout, QScrollArea, QGroupBox, QCheckBox,
    QLineEdit, QMessageBox, QSplitter, QFrame, QProgressDialog,
    QTabWidget, QRadioButton, QButtonGroup, QMenu, QToolButton,
    QStatusBar, QToolBar, QSizePolicy, QDialog, QDialogButtonBox,
    QPlainTextEdit, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QRect, QPoint,QPointF, QSize, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QFont, QCursor,
    QKeySequence, QShortcut, QIcon, QTransform, QAction, QClipboard
)


class ImageLoaderThread(QThread):
    """后台加载图片线程"""
    image_loaded = pyqtSignal(str, QPixmap, int, int) 
    finished_loading = pyqtSignal()
    
    def __init__(self, image_paths, max_size=800, auto_crop=False, crop_center=None, force_full=False):
        super().__init__()
        self.image_paths = image_paths
        self.max_size = max_size
        # 如果强制要求显示原图(用于让用户选坐标)，则临时关闭裁剪
        self.auto_crop = auto_crop and not force_full 
        self.crop_center = crop_center  # 新增：(x, y) 坐标
        self._is_running = True
    
    def run(self):
        for path in self.image_paths:
            if not self._is_running: break
            try:
                img = Image.open(path)
                
                # === 核心逻辑：基于指定中心进行裁剪 ===
                if self.auto_crop:
                    w, h = img.size
                    target_w, target_h = 392, 311
                    
                    if self.crop_center:
                        cx, cy = self.crop_center
                    else:
                        cx, cy = w // 2, h // 2
                    
                    # 确保裁剪框不会超出原图边界
                    left = max(0, min(cx - target_w // 2, w - target_w))
                    top = max(0, min(cy - target_h // 2, h - target_h))
                    right = left + target_w
                    bottom = top + target_h
                    img = img.crop((left, top, right, bottom))
                # ====================================
                
                w, h = img.size
                scale = min(self.max_size / w, self.max_size / h, 1.0) if w > 0 and h > 0 else 1.0
                if scale < 1.0:
                    new_w, new_h = int(w * scale), int(h * scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                else:
                    new_w, new_h = w, h
                
                if img.mode == 'RGB':
                    data = img.tobytes('raw', 'RGB')
                    qimg = QImage(data, new_w, new_h, new_w * 3, QImage.Format.Format_RGB888)
                elif img.mode == 'RGBA':
                    data = img.tobytes('raw', 'RGBA')
                    qimg = QImage(data, new_w, new_h, new_w * 4, QImage.Format.Format_RGBA8888)
                else:
                    img = img.convert('RGB')
                    data = img.tobytes('raw', 'RGB')
                    qimg = QImage(data, new_w, new_h, new_w * 3, QImage.Format.Format_RGB888)
                
                pixmap = QPixmap.fromImage(qimg)
                self.image_loaded.emit(path, pixmap, w, h)
            except Exception as e:
                print(f"加载图片失败 {path}: {e}")
        self.finished_loading.emit()
    def stop(self):
        self._is_running = False


class MagnifierWidget(QLabel):
    """放大镜组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 300)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_pixmap = None
        self.zoom_factor = 4.0
        self.center_pos = QPoint(150, 150)
        self.show_crosshair = True
        self.crosshair_color = QColor(255, 0, 0)
        self.setText("将鼠标悬停在图片上\n查看放大区域")
        self.setStyleSheet("""
            border: 2px solid #2196F3; 
            background-color: #1a1a1a;
            color: #888;
            font-size: 12px;
        """)
    
    def set_source(self, pixmap):
        self.source_pixmap = pixmap
        self.update_magnifier()
    
    def set_zoom_factor(self, factor):
        self.zoom_factor = factor
        self.update_magnifier()
    
    def set_center(self, pos):
        """pos 是 UI 缩放图的坐标"""
        self.center_pos = pos
        self.update_magnifier()
    
    def update_magnifier(self):
        if self.source_pixmap is None or self.source_pixmap.isNull():
            return
        
        src_w = self.source_pixmap.width()
        src_h = self.source_pixmap.height()
        
        # 计算截取区域大小
        view_w = int(self.width() / self.zoom_factor)
        view_h = int(self.height() / self.zoom_factor)
        
        x = self.center_pos.x() - view_w // 2
        y = self.center_pos.y() - view_h // 2
        
        # 严格边界处理：防止在边缘时放大镜变形或出现黑边
        x = max(0, min(x, src_w - view_w))
        y = max(0, min(y, src_h - view_h))
        
        rect = QRect(x, y, view_w, view_h)
        cropped = self.source_pixmap.copy(rect)
        
        # 强制铺满，且使用 FastTransformation (最近邻插值) 避免底层视觉任务中的像素被 UI 平滑掉
        scaled = cropped.scaled(self.width(), self.height(), 
                                Qt.AspectRatioMode.IgnoreAspectRatio,
                                Qt.TransformationMode.FastTransformation)
        
        # 绘制十字线
        if self.show_crosshair:
            painter = QPainter(scaled)
            pen = QPen(self.crosshair_color, 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            cx = scaled.width() // 2
            cy = scaled.height() // 2
            painter.drawLine(cx, 0, cx, scaled.height())
            painter.drawLine(0, cy, scaled.width(), cy)
            painter.end()
        
        self.setPixmap(scaled)


class ImageLabel(QLabel):
    """支持无限缩放、平移拖拽，且网格布局绝对自适应的图片查看器"""
    mouse_moved = pyqtSignal(QPoint)
    mouse_pressed = pyqtSignal(QPoint)
    region_selected = pyqtSignal(QRect)
    
    def __init__(self, image_path, original_size, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.original_size = original_size
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("border: 1px solid #444; background-color: #222;")
        self.setMouseTracking(True) 
        
        # 视图控制 (虚拟相机)
        self.view_scale = 1.0       
        self.view_offset = QPointF(0.0, 0.0) 
        self.user_interacted = False  # 核心修复：记录用户是否手动缩放过
        
        # 拖拽平移控制
        self.is_panning = False
        self.pan_start_pos = QPoint()
        
        # 选择模式
        self.select_mode = False
        self.selection_start = None
        self.selection_end = None
        self.current_selection = None
        
        # 显示信息
        self.info_text = ""
        self.show_info = True
        self.zoom_factor = 4.0 
        self.pick_center_mode = False
        self.hover_pos = None
        self.pick_center_mode = False
        self.fixed_region_mode = False  # 新增：固定红框拾取模式
        self.hover_pos = None
    
        # 增加一个新的信号
    center_picked = pyqtSignal(QPoint)

    # ================= 核心修复部分开始 =================
    
    def minimumSizeHint(self):
        """打破 QLabel 默认按图片物理尺寸撑大布局的限制，允许控件被无限缩小"""
        return QSize(50, 50)

    def sizeHint(self):
        """给所有图片一个统一的初始期望大小，确保网格布局绝对平分空间"""
        return QSize(300, 300)

    def fit_to_window(self):
        """计算让图片完美居中并自适应控件大小的矩阵"""
        if not hasattr(self, '_pixmap') or self._pixmap is None: return
        lbl_w, lbl_h = self.width(), self.height()
        px_w, px_h = self._pixmap.width(), self._pixmap.height()
        if px_w == 0 or px_h == 0 or lbl_w < 10 or lbl_h < 10: return
        
        # 计算能完整显示的最大缩放比例 (留出3%的边距让视觉更舒服)
        self.view_scale = min(lbl_w / px_w, lbl_h / px_h) * 0.97
        
        # 绝对居中偏移
        cx = (lbl_w - px_w * self.view_scale) / 2.0
        cy = (lbl_h - px_h * self.view_scale) / 2.0
        self.view_offset = QPointF(cx, cy)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 只要用户没有手动放大/拖拽过，窗口调整大小时自动重新居中自适应
        if not self.user_interacted:
            self.fit_to_window()

    def mouseDoubleClickEvent(self, event):
        """双击恢复自适应全貌显示"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.user_interacted = False
            self.fit_to_window()
            
    # ================= 核心修复部分结束 =================

    def setPixmap(self, pixmap):
        super().setPixmap(pixmap)
        self._pixmap = pixmap
        self.user_interacted = False
        self.fit_to_window()

    def get_image_pos(self, widget_pos):
        if not hasattr(self, '_pixmap') or self._pixmap is None: return QPoint(0, 0)
        px_x = (widget_pos.x() - self.view_offset.x()) / self.view_scale
        px_y = (widget_pos.y() - self.view_offset.y()) / self.view_scale
        orig_w, orig_h = self.original_size
        px_w, px_h = self._pixmap.width(), self._pixmap.height()
        
        if px_w > 0 and px_h > 0:
            final_x = int(px_x * (orig_w / px_w))
            final_y = int(px_y * (orig_h / px_h))
            final_x = max(0, min(final_x, orig_w))
            final_y = max(0, min(final_y, orig_h))
            return QPoint(final_x, final_y)
        return QPoint(0, 0)

    def get_widget_rect(self, img_rect):
        if not hasattr(self, '_pixmap') or self._pixmap is None: return QRect()
        orig_w, orig_h = self.original_size
        px_w, px_h = self._pixmap.width(), self._pixmap.height()
        
        if orig_w > 0 and orig_h > 0:
            px_x = img_rect.x() * (px_w / orig_w)
            px_y = img_rect.y() * (px_h / orig_h)
            px_w_rect = img_rect.width() * (px_w / orig_w)
            px_h_rect = img_rect.height() * (px_h / orig_h)
            
            w_x = int(px_x * self.view_scale + self.view_offset.x())
            w_y = int(px_y * self.view_scale + self.view_offset.y())
            w_w = int(px_w_rect * self.view_scale)
            w_h = int(px_h_rect * self.view_scale)
            return QRect(w_x, w_y, w_w, w_h)
        return QRect()

    def wheelEvent(self, event):
        if not hasattr(self, '_pixmap') or self._pixmap is None: return
        self.user_interacted = True 
        zoom_in = event.angleDelta().y() > 0
        factor = 1.15 if zoom_in else 1.0 / 1.15
        
        new_scale = self.view_scale * factor
        if new_scale < 0.1 or new_scale > 50.0: return
        
        mouse_pos = event.position()
        self.view_offset.setX(mouse_pos.x() - (mouse_pos.x() - self.view_offset.x()) * factor)
        self.view_offset.setY(mouse_pos.y() - (mouse_pos.y() - self.view_offset.y()) * factor)
        
        self.view_scale = new_scale
        self.update()
        
        pos = self.get_image_pos(QPoint(int(mouse_pos.x()), int(mouse_pos.y())))
        self.mouse_moved.emit(pos)

    def mouseMoveEvent(self, event):
        pos = self.get_image_pos(event.pos())
        self.hover_pos = pos  
        self.mouse_moved.emit(pos)
        
        if self.is_panning:
            delta = event.pos() - self.pan_start_pos
            self.view_offset.setX(self.view_offset.x() + delta.x())
            self.view_offset.setY(self.view_offset.y() + delta.y())
            self.pan_start_pos = event.pos()
            self.update()
        elif self.select_mode and self.selection_start:
            self.selection_end = event.pos()
            self.update()
        elif self.pick_center_mode or self.fixed_region_mode:  # 修改：固定红框模式也需要实时刷新
            self.update() 
            
        if hasattr(self, '_pixmap') and self._pixmap:
            self.info_text = f"原图坐标: ({pos.x()}, {pos.y()}) | 缩放: {self.view_scale*100:.1f}%"
            self.update()

    def mousePressEvent(self, event):
        pos = self.get_image_pos(event.pos())
        self.mouse_pressed.emit(pos)
        
        if event.button() == Qt.MouseButton.LeftButton and self.pick_center_mode:
            self.center_picked.emit(pos)
            return
            
        # === 新增：如果在固定红框模式下，左键点击直接生成 101x51 的框 ===
        if event.button() == Qt.MouseButton.LeftButton and self.fixed_region_mode:
            target_w, target_h = 101, 51
            cx, cy = pos.x(), pos.y()
            orig_w, orig_h = self.original_size
            
            # 边界保护
            left = max(0, min(cx - target_w // 2, orig_w - target_w))
            top = max(0, min(cy - target_h // 2, orig_h - target_h))
            
            self.current_selection = QRect(left, top, target_w, target_h)
            self.region_selected.emit(self.current_selection) # 借用原有的信号发射出去
            
            self.fixed_region_mode = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.update()
            return
        # ==========================================================
            
        if event.button() == Qt.MouseButton.LeftButton and self.select_mode:
            self.selection_start = event.pos()
            self.selection_end = event.pos()
        elif event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self.user_interacted = True 
            self.is_panning = True
            self.pan_start_pos = event.pos()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
    def mouseReleaseEvent(self, event):
        if self.is_panning:
            self.is_panning = False
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor if self.select_mode else Qt.CursorShape.ArrowCursor))
            
        if event.button() == Qt.MouseButton.LeftButton and self.select_mode and self.selection_start:
            self.selection_end = event.pos()
            p1 = self.get_image_pos(self.selection_start)
            p2 = self.get_image_pos(self.selection_end)
            x, y = min(p1.x(), p2.x()), min(p1.y(), p2.y())
            w, h = abs(p2.x() - p1.x()), abs(p2.y() - p1.y())
            
            if w > 5 and h > 5:
                self.current_selection = QRect(x, y, w, h)
                self.region_selected.emit(self.current_selection)
            
            self.selection_start = None
            self.selection_end = None
            self.select_mode = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.update()

    def paintEvent(self, event):
        if not hasattr(self, '_pixmap') or self._pixmap is None: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        transform = QTransform()
        transform.translate(self.view_offset.x(), self.view_offset.y())
        transform.scale(self.view_scale, self.view_scale)
        painter.setTransform(transform)
        painter.drawPixmap(0, 0, self._pixmap)
        
        # 1. 自由拖拽框
        if self.select_mode and self.selection_start and self.selection_end:
            painter.resetTransform() 
            pen = QPen(QColor(255, 0, 0), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            x, y = min(self.selection_start.x(), self.selection_end.x()), min(self.selection_start.y(), self.selection_end.y())
            w, h = abs(self.selection_end.x() - self.selection_start.x()), abs(self.selection_end.y() - self.selection_start.y())
            painter.drawRect(x, y, w, h)

        # 2. 已确认的学术红框
        if self.current_selection:
            painter.resetTransform()
            pen = QPen(QColor(255, 0, 0), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            rect_view = self.get_widget_rect(self.current_selection)
            painter.drawRect(rect_view)

        # 3. 绿色的 392x311 裁剪预览框
        if self.pick_center_mode and self.hover_pos:
            painter.resetTransform()
            pen = QPen(QColor(0, 255, 0), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            target_w, target_h = 392, 311
            cx, cy = self.hover_pos.x(), self.hover_pos.y()
            orig_w, orig_h = self.original_size
            
            left = max(0, min(cx - target_w // 2, orig_w - target_w))
            top = max(0, min(cy - target_h // 2, orig_h - target_h))
            rect_view = self.get_widget_rect(QRect(left, top, target_w, target_h))
            painter.drawRect(rect_view)

        # === 新增：红色的 101x51 局部放大预览框 ===
        if self.fixed_region_mode and self.hover_pos:
            painter.resetTransform()
            pen = QPen(QColor(255, 0, 0), 2, Qt.PenStyle.DashLine) # 红色虚线预览
            painter.setPen(pen)
            
            target_w, target_h = 101, 51
            cx, cy = self.hover_pos.x(), self.hover_pos.y()
            orig_w, orig_h = self.original_size
            
            left = max(0, min(cx - target_w // 2, orig_w - target_w))
            top = max(0, min(cy - target_h // 2, orig_h - target_h))
            rect_view = self.get_widget_rect(QRect(left, top, target_w, target_h))
            painter.drawRect(rect_view)
        # =======================================

        # 4. 绘制底部信息文字
        painter.resetTransform()
        if self.show_info and self.info_text:
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(self.info_text)
            painter.fillRect(5, self.height() - 25, tw + 10, 20, QColor(0, 0, 0, 150))
            painter.drawText(10, self.height() - 10, self.info_text)
            
        painter.end()

class ComparisonViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("论文方法对比图查看工具 (Paper Comparison Viewer)")
        self.setGeometry(100, 100, 1600, 1000)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                font-family: "Microsoft YaHei", "Segoe UI";
                font-size: 12px;
            }
            QPushButton {
                background-color: #3c3c3c;
                border: 1px solid #555;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border-color: #2196F3;
            }
            QPushButton:pressed {
                background-color: #2196F3;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #444;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                margin: -5px 0;
                background: #2196F3;
                border-radius: 8px;
            }
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #3c3c3c;
                border: 1px solid #555;
                padding: 4px;
                border-radius: 3px;
            }
            QGroupBox {
                border: 1px solid #555;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QScrollArea {
                border: none;
            }
            QLabel {
                color: #e0e0e0;
            }
            QStatusBar {
                background-color: #1a1a1a;
            }
            QToolBar {
                background-color: #333;
                border: none;
                spacing: 5px;
            }
            QTableWidget {
                background-color: #2b2b2b;
                alternate-background-color: #333;
                gridline-color: #444;
            }
            QHeaderView::section {
                background-color: #3c3c3c;
                padding: 5px;
                border: 1px solid #555;
            }
        """)
        
        self.image_paths = []
        self.image_labels = {}  # path -> ImageLabel
        self.image_pixmaps = {}  # path -> QPixmap (显示尺寸)
        self.original_sizes = {}  # path -> (w, h)
        self.current_folder = ""
        self.loader_thread = None
        
        # 放大镜同步
        self.magnifier = None
        self.zoom_factor = 4.0
        self.sync_magnifier = True
        self.selected_region = None
        
        # 保存设置
        self.save_format = "PNG"
        self.save_quality = 95
        self.save_dpi = 300
        self.add_border = True
        self.add_label = True
        self.border_width = 2
        self.border_color = QColor(255, 255, 255)
        self.crop_center = None      # 记录中心点 (x, y)
        self.picking_center = False  # 记录当前是否处于拾取模式
        
        self.init_ui()
        self.setup_shortcuts()
    
    def init_ui(self):
        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # ===== 左侧：图片展示区 =====
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 工具栏
        toolbar = QToolBar()
        left_layout.addWidget(toolbar)
        
        self.btn_open = QPushButton("📁 打开文件夹")
        self.btn_open.setToolTip("Ctrl+O")
        self.btn_open.clicked.connect(self.open_folder)
        toolbar.addWidget(self.btn_open)
        
        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.clicked.connect(self.refresh_images)
        toolbar.addWidget(self.btn_refresh)

        # === 新增：固定尺寸裁剪复选框 ===
        toolbar.addSeparator()
        self.chk_auto_crop = QCheckBox("✂️ 强制裁剪为 392x311")
        self.chk_auto_crop.setToolTip("开启后，加载和保存的所有图片都会被中心裁剪为 392x311 尺寸")
        # 勾选/取消勾选时，自动刷新图片
        self.chk_auto_crop.stateChanged.connect(self.refresh_images)
        toolbar.addWidget(self.chk_auto_crop)
        # ===============================
        # === 新增：选取中心按钮 ===
        self.btn_pick_center = QPushButton("🎯 选取裁剪区域")
        self.btn_pick_center.setToolTip("点击后在原图上移动鼠标，点击确定 392x311 的裁剪中心")
        self.btn_pick_center.setCheckable(True)
        self.btn_pick_center.clicked.connect(self.toggle_pick_center)
        toolbar.addWidget(self.btn_pick_center)
        # =======================
        
        toolbar.addSeparator()
        
        self.btn_select_region = QPushButton("⬚ 自由画框")
        self.btn_select_region.setCheckable(True)
        self.btn_select_region.clicked.connect(self.toggle_select_mode)
        self.btn_select_region.setToolTip("按住左键拖拽，自由框选对比区域")
        toolbar.addWidget(self.btn_select_region)
        
        # === 新增：固定画框按钮 ===
        self.btn_fixed_region = QPushButton("📌 固定画框 (101x51)")
        self.btn_fixed_region.setCheckable(True)
        self.btn_fixed_region.clicked.connect(self.toggle_fixed_region)
        self.btn_fixed_region.setToolTip("点击后在图片上移动预览，左键点击确认 101x51 的红框")
        toolbar.addWidget(self.btn_fixed_region)
        # =======================
        
        self.btn_clear_region = QPushButton("✕ 清除区域")
        self.btn_clear_region.clicked.connect(self.clear_region)
        toolbar.addWidget(self.btn_clear_region)
        
        toolbar.addSeparator()
        
        self.btn_save_all = QPushButton("💾 保存全部")
        self.btn_save_all.clicked.connect(self.save_all_images)
        toolbar.addWidget(self.btn_save_all)
        
        self.btn_save_region = QPushButton("🔍 保存区域")
        self.btn_save_region.clicked.connect(self.save_region)
        toolbar.addWidget(self.btn_save_region)
        
        # 图片滚动区
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_layout.addWidget(self.scroll_area)
        
        self.images_container = QWidget()
        self.images_grid = QGridLayout(self.images_container)
        self.images_grid.setSpacing(10)
        self.images_grid.setContentsMargins(10, 10, 10, 10)
        self.scroll_area.setWidget(self.images_container)
        
        splitter.addWidget(left_widget)
        
        # ===== 右侧：控制面板 =====
        right_widget = QWidget()
        right_widget.setMaximumWidth(350)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)
        
        # --- 放大镜控制 ---
        mag_group = QGroupBox("🔍 放大镜设置")
        mag_layout = QVBoxLayout(mag_group)
        
        # 同步开关
        self.chk_sync = QCheckBox("同步所有图片放大镜")
        self.chk_sync.setChecked(True)
        self.chk_sync.stateChanged.connect(self.on_sync_changed)
        mag_layout.addWidget(self.chk_sync)
        
        # 放大倍数
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("放大倍数:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 200)  # 1.0x ~ 20.0x
        self.zoom_slider.setValue(int(self.zoom_factor * 10))
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)
        self.zoom_label = QLabel(f"{self.zoom_factor:.1f}x")
        zoom_layout.addWidget(self.zoom_label)
        mag_layout.addLayout(zoom_layout)
        
        # 十字线
        self.chk_crosshair = QCheckBox("显示十字线")
        self.chk_crosshair.setChecked(True)
        self.chk_crosshair.stateChanged.connect(self.on_crosshair_changed)
        mag_layout.addWidget(self.chk_crosshair)
        
        # 放大镜显示
        self.magnifier = MagnifierWidget()
        mag_layout.addWidget(self.magnifier, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 区域信息
        self.region_info = QLabel("未选择区域")
        self.region_info.setStyleSheet("color: #888; font-size: 11px;")
        mag_layout.addWidget(self.region_info)
        
        right_layout.addWidget(mag_group)
        
        # --- 保存设置 ---
        save_group = QGroupBox("💾 保存设置")
        save_layout = QVBoxLayout(save_group)
        
        # 保存格式
        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("格式:"))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["PNG", "JPEG", "TIFF", "BMP", "WebP", "PDF"])
        self.fmt_combo.setCurrentText(self.save_format)
        self.fmt_combo.currentTextChanged.connect(self.on_format_changed)
        fmt_layout.addWidget(self.fmt_combo)
        save_layout.addLayout(fmt_layout)
        
        # 质量
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("质量:"))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(self.save_quality)
        quality_layout.addWidget(self.quality_spin)
        quality_layout.addWidget(QLabel("%"))
        save_layout.addLayout(quality_layout)
        
        # DPI
        dpi_layout = QHBoxLayout()
        dpi_layout.addWidget(QLabel("DPI:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(self.save_dpi)
        self.dpi_spin.setSingleStep(50)
        dpi_layout.addWidget(self.dpi_spin)
        save_layout.addLayout(dpi_layout)
        
        # 选项
        self.chk_border = QCheckBox("原图添加外边框 (保存全部时)")
        self.chk_border.setChecked(False)
        save_layout.addWidget(self.chk_border)
        
        self.chk_region_border = QCheckBox("局部保留红边框 (分别保存时)")
        self.chk_region_border.setChecked(True)
        save_layout.addWidget(self.chk_region_border)
        
        # 保存按钮
        btn_layout = QHBoxLayout()
        self.btn_save_current = QPushButton("保存当前视图")
        self.btn_save_current.clicked.connect(self.save_current_view)
        btn_layout.addWidget(self.btn_save_current)
        
        self.btn_save_individual = QPushButton("分别保存")
        self.btn_save_individual.clicked.connect(self.save_individual)
        btn_layout.addWidget(self.btn_save_individual)
        save_layout.addLayout(btn_layout)
        
        right_layout.addWidget(save_group)
        
        # --- 图片列表 ---
        list_group = QGroupBox("📋 图片列表")
        list_layout = QVBoxLayout(list_group)
        
        self.image_table = QTableWidget()
        self.image_table.setColumnCount(3)
        self.image_table.setHorizontalHeaderLabels(["文件名", "尺寸", "操作"])
        self.image_table.horizontalHeader().setStretchLastSection(True)
        self.image_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.image_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.image_table.setAlternatingRowColors(True)
        self.image_table.setMaximumHeight(200)
        list_layout.addWidget(self.image_table)
        
        right_layout.addWidget(list_group)
        
        # 添加弹性空间
        right_layout.addStretch()
        
        # 状态信息
        self.status_label = QLabel("就绪 | 未加载图片")
        self.status_label.setStyleSheet("color: #888; padding: 5px;")
        right_layout.addWidget(self.status_label)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([1200, 400])
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("准备就绪")
    def toggle_fixed_region(self):
        is_selecting = self.btn_fixed_region.isChecked()
        
        # 互斥逻辑：如果开启了固定画框，就关掉其他画框模式
        if is_selecting:
            self.btn_select_region.setChecked(False)
            self.btn_pick_center.setChecked(False)
            self.picking_center = False
            self.toggle_select_mode() 
        
        for label in self.image_labels.values():
            label.fixed_region_mode = is_selecting
            if is_selecting:
                label.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            else:
                label.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        
        if is_selecting:
            self.status_bar.showMessage("👉 请在图片上移动鼠标预览，点击左键确定 101x51 的对比红框")
        else:
            self.status_bar.showMessage("已取消选取")
    def on_auto_crop_changed(self):
        # 只要不是在选坐标的过程中，勾选/取消勾选都重新加载
        if not self.picking_center:
            self.load_images_async()

    def toggle_pick_center(self):
        self.picking_center = self.btn_pick_center.isChecked()
        if self.picking_center:
            self.btn_select_region.setChecked(False) 
            self.toggle_select_mode()
            self.status_bar.showMessage("👉 请在任意图片上移动鼠标预览，点击左键确定 392x311 裁剪区域")
            # 临时加载一次全尺寸原图供用户挑选
            self.load_images_async(force_full=True)
        else:
            self.status_bar.showMessage("已取消选取")
            self.load_images_async()

    def on_center_picked(self, pos, path):
        if not self.picking_center: return
        self.crop_center = (pos.x(), pos.y())
        self.picking_center = False
        self.btn_pick_center.setChecked(False)
        self.chk_auto_crop.setChecked(True) # 强制开启裁剪
        self.status_bar.showMessage(f"✅ 已成功应用新的裁剪区域: 中心点 ({pos.x()}, {pos.y()})")
        self.load_images_async()
    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_folder)
        QShortcut(QKeySequence("Ctrl+R"), self, self.refresh_images)
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_all_images)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)
        QShortcut(QKeySequence("+"), self, lambda: self.adjust_zoom(0.5))
        QShortcut(QKeySequence("-"), self, lambda: self.adjust_zoom(-0.5))
        QShortcut(QKeySequence("Esc"), self, self.clear_region)
    
    def adjust_zoom(self, delta):
        new_val = self.zoom_slider.value() + int(delta * 10)
        new_val = max(10, min(200, new_val))
        self.zoom_slider.setValue(new_val)
    
    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹", self.current_folder)
        if folder:
            self.current_folder = folder
            self.load_images_from_folder(folder)
    
    def load_images_from_folder(self, folder):
        # 支持的图片格式
        extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.tiff', '*.tif', '*.webp', '*.gif']
        self.image_paths = []
        for ext in extensions:
            self.image_paths.extend(glob.glob(os.path.join(folder, ext)))
            self.image_paths.extend(glob.glob(os.path.join(folder, ext.upper())))
        
        self.image_paths = sorted(list(set(self.image_paths)))
        
        if not self.image_paths:
            QMessageBox.information(self, "提示", "未找到图片文件")
            return
        
        self.status_bar.showMessage(f"找到 {len(self.image_paths)} 张图片，正在加载...")
        self.load_images_async()
    
    def load_images_async(self, force_full=False):
        self.clear_grid()
        self.image_labels.clear()
        self.image_pixmaps.clear()
        self.original_sizes.clear()
        self.image_table.setRowCount(0)
        
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
            self.loader_thread.wait()
        
        is_crop = self.chk_auto_crop.isChecked()
        # 将配置传给线程
        self.loader_thread = ImageLoaderThread(
            self.image_paths, max_size=600, 
            auto_crop=is_crop, crop_center=self.crop_center, force_full=force_full
        )
        self.loader_thread.image_loaded.connect(self.on_image_loaded)
        self.loader_thread.finished_loading.connect(self.on_loading_finished)
        self.loader_thread.start()

    def on_image_loaded(self, path, pixmap, orig_w, orig_h):
        self.image_pixmaps[path] = pixmap
        self.original_sizes[path] = (orig_w, orig_h)
        
        label = ImageLabel(path, (orig_w, orig_h))
        label.setPixmap(pixmap)
        
        # === 同步当前模式和事件 ===
        label.pick_center_mode = self.picking_center
        label.fixed_region_mode = self.btn_fixed_region.isChecked() # 新增：同步固定红框模式
        label.center_picked.connect(lambda pos, p=path: self.on_center_picked(pos, p))
        # ==========================
        
        label.region_selected.connect(lambda rect, p=path: self.on_region_selected(rect, p))
        self.image_labels[path] = label
        
        row = self.image_table.rowCount()
        self.image_table.insertRow(row)
        name_item = QTableWidgetItem(os.path.basename(path))
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.image_table.setItem(row, 0, name_item)
        size_item = QTableWidgetItem(f"{orig_w}x{orig_h}")
        size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.image_table.setItem(row, 1, size_item)
        btn_remove = QPushButton("移除")
        btn_remove.clicked.connect(lambda checked, r=row: self.remove_image(r))
        self.image_table.setCellWidget(row, 2, btn_remove)
    
    def on_loading_finished(self):
        self.refresh_grid_layout()
        self.status_bar.showMessage(f"已加载 {len(self.image_paths)} 张图片")
        self.status_label.setText(f"文件夹: {self.current_folder}\n图片数: {len(self.image_paths)}")
    
    def refresh_grid_layout(self):
        # 清空网格
        while self.images_grid.count():
            item = self.images_grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        
        # 重新排列
        cols = min(4, max(2, len(self.image_labels)))
        for idx, (path, label) in enumerate(self.image_labels.items()):
            row = idx // cols
            col = idx % cols
            
            # 创建容器
            container = QWidget()
            vlayout = QVBoxLayout(container)
            vlayout.setContentsMargins(5, 5, 5, 5)
            vlayout.setSpacing(5)
            
            # 方法名标签
            method_name = os.path.splitext(os.path.basename(path))[0]
            name_label = QLabel(method_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setStyleSheet("font-weight: bold; color: #2196F3; font-size: 13px;")
            vlayout.addWidget(name_label)
            
            # 图片
            vlayout.addWidget(label, 1)
            
            # 尺寸信息
            ow, oh = self.original_sizes.get(path, (0, 0))
            info = QLabel(f"{ow} x {oh}")
            info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info.setStyleSheet("color: #888; font-size: 10px;")
            vlayout.addWidget(info)
            
            self.images_grid.addWidget(container, row, col)
    
    def clear_grid(self):
        while self.images_grid.count():
            item = self.images_grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
    
    def refresh_images(self):
        if self.current_folder:
            self.load_images_from_folder(self.current_folder)
    
    def remove_image(self, row):
        if row < 0 or row >= len(self.image_paths):
            return
        path = self.image_paths[row]
        
        if path in self.image_labels:
            del self.image_labels[path]
        if path in self.image_pixmaps:
            del self.image_pixmaps[path]
        if path in self.original_sizes:
            del self.original_sizes[path]
        
        self.image_paths.pop(row)
        self.image_table.removeRow(row)
        self.refresh_grid_layout()
    
    def on_mouse_moved(self, pos, path):
        for label in self.image_labels.values():
            label.zoom_factor = self.zoom_factor
            
        if self.magnifier and path in self.image_pixmaps:
            px = self.image_pixmaps[path]
            orig_w, orig_h = self.original_sizes[path]
            
            # 核心修复：将鼠标的原图坐标(pos)等比例转换为UI缩放图的坐标
            if orig_w > 0 and orig_h > 0:
                scaled_x = int(pos.x() * (px.width() / orig_w))
                scaled_y = int(pos.y() * (px.height() / orig_h))
                
                self.magnifier.set_source(px)
                self.magnifier.set_center(QPoint(scaled_x, scaled_y))
            
            # 同步到其他图片
            if self.sync_magnifier:
                for p, label in self.image_labels.items():
                    if p != path:
                        # 这里可以留空或添加同步逻辑
                        pass
    
    def on_mouse_pressed(self, pos, path):
        pass
    
    def toggle_select_mode(self):
        is_selecting = self.btn_select_region.isChecked()
        for label in self.image_labels.values():
            label.select_mode = is_selecting
            if is_selecting:
                label.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            else:
                label.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        
        if is_selecting:
            self.status_bar.showMessage("框选模式：在所有图片上拖拽选择区域")
        else:
            self.status_bar.showMessage("查看模式")
    
    def on_region_selected(self, rect, path):
        self.selected_region = rect
        self.region_info.setText(f"选中区域: ({rect.x()}, {rect.y()}) {rect.width()}x{rect.height()}")
        self.btn_select_region.setChecked(False)
        self.btn_fixed_region.setChecked(False) # 增加关闭固定按钮状态
        
        self.toggle_select_mode() 
        self.toggle_fixed_region() # 取消模式状态
        
        # 高亮显示区域
        for label in self.image_labels.values():
            label.current_selection = rect
            label.update()

    def clear_region(self):
        self.selected_region = None
        self.region_info.setText("未选择区域")
        for label in self.image_labels.values():
            label.current_selection = None
            label.update()
        self.btn_select_region.setChecked(False)
        self.btn_fixed_region.setChecked(False) # 增加关闭固定按钮状态
        self.toggle_select_mode()
        self.toggle_fixed_region() # 增加关闭固定状态
    
    def on_zoom_changed(self, value):
        self.zoom_factor = value / 10.0
        self.zoom_label.setText(f"{self.zoom_factor:.1f}x")
        if self.magnifier:
            self.magnifier.set_zoom_factor(self.zoom_factor)
    
    def on_sync_changed(self, state):
        self.sync_magnifier = state == Qt.CheckState.Checked.value
    
    def on_crosshair_changed(self, state):
        if self.magnifier:
            self.magnifier.show_crosshair = state == Qt.CheckState.Checked.value
            self.magnifier.update_magnifier()
    
    def on_format_changed(self, fmt):
        self.save_format = fmt
    
    def get_save_options(self):
        return {
            'format': self.save_format,
            'quality': self.quality_spin.value(),
            'dpi': self.dpi_spin.value(),
            'border': self.chk_border.isChecked(),           
            'region_border': self.chk_region_border.isChecked(),
            'auto_crop': self.chk_auto_crop.isChecked()  # 新增
        }
    
    def save_all_images(self):
        if not self.image_paths:
            QMessageBox.warning(self, "警告", "没有图片可保存")
            return
        
        folder = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if not folder:
            return
        
        opts = self.get_save_options()
        
        progress = QProgressDialog("正在保存...", "取消", 0, len(self.image_paths), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        for i, path in enumerate(self.image_paths):
            if progress.wasCanceled():
                break
            
            try:
                self.save_single_image(path, folder, opts)
            except Exception as e:
                print(f"保存失败 {path}: {e}")
            
            progress.setValue(i + 1)
        
        progress.setValue(len(self.image_paths))
        QMessageBox.information(self, "完成", f"图片已保存到: {folder}")
    
    def save_single_image(self, path, folder, opts):
        """保存单张图片：仅在图上绘制学术红框，不进行多余裁剪"""
        img = Image.open(path)
        
        # === 动态坐标保存逻辑 ===
        if opts.get('auto_crop', False):
            w, h = img.size
            tw, th = 392, 311
            if self.crop_center:
                cx, cy = self.crop_center
            else:
                cx, cy = w // 2, h // 2

            left = max(0, min(cx - tw // 2, w - tw))
            top = max(0, min(cy - th // 2, h - th))
            right = left + tw
            bottom = top + th
            img = img.crop((left, top, right, bottom))
        
        if self.selected_region:
            # 直接在全图上画红框
            draw = ImageDraw.Draw(img)
            r = self.selected_region
            line_width = max(2, img.width // 250) 
            draw.rectangle(
                [r.x(), r.y(), r.x() + r.width(), r.y() + r.height()],
                outline=(255, 0, 0), 
                width=line_width
            )
        
        # 添加边框
        if opts.get('border', False):
            border_w = 3
            new_w = img.width + border_w * 2
            new_h = img.height + border_w * 2
            bordered = Image.new('RGB', (new_w, new_h), (255, 255, 255))
            bordered.paste(img, (border_w, border_w))
            img = bordered
        
        # 保存
        base_name = os.path.splitext(os.path.basename(path))[0]
        ext = opts.get('format', 'PNG').lower()
        if ext == 'jpeg':
            ext = 'jpg'
        
        save_path = os.path.join(folder, f"{base_name}_full.{ext}")
        
        save_kwargs = {'dpi': (opts.get('dpi', 300), opts.get('dpi', 300))}
        if opts.get('format') in ['JPEG', 'WEBP']:
            save_kwargs['quality'] = opts.get('quality', 95)
            if img.mode == 'RGBA':
                img = img.convert('RGB')
        
        img.save(save_path, **save_kwargs)
    
    def save_region(self):
        """保存选中的区域：将各图片局部抠出并单独保存为文件"""
        if not self.selected_region:
            QMessageBox.warning(self, "警告", "请先点击 '⬚ 选择区域' 并画出红框")
            return
        
        if not self.image_paths:
            return
        
        folder = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if not folder:
            return
        
        r = self.selected_region
        opts = self.get_save_options()
        ext = opts['format'].lower()
        if ext == 'jpeg':
            ext = 'jpg'
        
        progress = QProgressDialog("正在单独保存各区域...", "取消", 0, len(self.image_paths), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        for i, path in enumerate(self.image_paths):
            if progress.wasCanceled():
                break
            
            try:
                # 直接操作原图，保证 100% 不会被压缩或裁剪
                img = Image.open(path)

                # === 动态坐标保存逻辑 ===
                if opts.get('auto_crop', False):
                    w, h = img.size
                    tw, th = 392, 311
                    if self.crop_center:
                        cx, cy = self.crop_center
                    else:
                        cx, cy = w // 2, h // 2

                    left = max(0, min(cx - tw // 2, w - tw))
                    top = max(0, min(cy - th // 2, h - th))
                    right = left + tw
                    bottom = top + th
                    img = img.crop((left, top, right, bottom))
                    
                x1 = max(0, r.x())
                y1 = max(0, r.y())
                x2 = min(img.width, r.x() + r.width())
                y2 = min(img.height, r.y() + r.height())
                
                if x2 > x1 and y2 > y1:
                    crop = img.crop((x1, y1, x2, y2))
                    
                    # 是否给裁剪出的小图添加红框 (根据 UI 勾选)
                    if opts['region_border']:
                        border_w = max(2, crop.width // 100)
                        bordered = Image.new('RGB', (crop.width + border_w*2, crop.height + border_w*2), (255, 0, 0))
                        bordered.paste(crop, (border_w, border_w))
                        crop = bordered

                    base_name = os.path.splitext(os.path.basename(path))[0]
                    save_path = os.path.join(folder, f"{base_name}_region.{ext}")
                    
                    save_kwargs = {'dpi': (opts['dpi'], opts['dpi'])}
                    if opts['format'] in ['JPEG', 'WEBP']:
                        save_kwargs['quality'] = opts['quality']
                        if crop.mode == 'RGBA':
                            crop = crop.convert('RGB')
                    
                    crop.save(save_path, **save_kwargs)
            except Exception as e:
                print(f"保存区域失败 {path}: {e}")
                
            progress.setValue(i + 1)
            
        QMessageBox.information(self, "完成", f"✅ 各图片区域已单独保存至:\n{folder}")
    
    def save_current_view(self):
        """保存当前视图为截图"""
        if not self.image_paths:
            return
        
        folder = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if not folder:
            return
        
        # 截取当前窗口
        pixmap = self.grab()
        save_path = os.path.join(folder, "screenshot.png")
        pixmap.save(save_path)
        QMessageBox.information(self, "完成", f"截图已保存到: {save_path}")
    
    def save_individual(self):
        """分别保存每张图片的选中红框区域，输出为论文所需的独立对比小图"""
        if not self.image_paths:
            QMessageBox.warning(self, "警告", "没有图片可保存")
            return
            
        if not self.selected_region:
            QMessageBox.warning(self, "警告", "请先点击 '⬚ 选择区域'，并在图上拖拽画出红框！")
            return

        # 选择保存目录
        folder = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if not folder:
            return

        # 获取保存格式
        opts = self.get_save_options()
        ext = opts['format'].lower()
        if ext == 'jpeg':
            ext = 'jpg'

        progress = QProgressDialog("正在生成各个方法的局部对比图...", "取消", 0, len(self.image_paths), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        for i, path in enumerate(self.image_paths):
            if progress.wasCanceled():
                break
                
            try:
                # 1. 打开原图 (保证高精度无损)
                img = Image.open(path)
                
                # 2. 映射你画的红框区域
                r = self.selected_region
                x1 = max(0, r.x())
                y1 = max(0, r.y())
                x2 = min(img.width, r.x() + r.width())
                y2 = min(img.height, r.y() + r.height())
                
                if x2 > x1 and y2 > y1:
                    crop = img.crop((x1, y1, x2, y2))
                else:
                    continue # 越界则跳过

                # 3. 添加学术标准的红色边框 (如果右侧面板勾选了'添加边框')
                if opts['border']:
                    # 根据切图大小自适应线宽，避免小图边框太粗
                    border_w = max(2, crop.width // 100) 
                    bordered = Image.new('RGB', (crop.width + border_w*2, crop.height + border_w*2), (255, 0, 0))
                    bordered.paste(crop, (border_w, border_w))
                    crop = bordered

                # 4. 生成文件名：原方法名_crop
                base_name = os.path.splitext(os.path.basename(path))[0]
                save_path = os.path.join(folder, f"{base_name}_crop.{ext}")

                # 5. 导出保存
                save_kwargs = {'dpi': (opts['dpi'], opts['dpi'])}
                if opts['format'] in ['JPEG', 'WEBP']:
                    save_kwargs['quality'] = opts['quality']
                    
                if crop.mode == 'RGBA':
                    crop = crop.convert('RGB')
                crop.save(save_path, **save_kwargs)

            except Exception as e:
                print(f"保存失败 {path}: {e}")

            progress.setValue(i + 1)

        QMessageBox.information(self, "完成", f"✅ 局部放大图已分别保存至:\n{folder}")
    
    def closeEvent(self, event):
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.stop()
            self.loader_thread.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 设置应用级样式
    app.setStyleSheet("""
        QToolTip {
            background-color: #333;
            color: #fff;
            border: 1px solid #555;
            padding: 5px;
        }
    """)
    
    viewer = ComparisonViewer()
    viewer.show()
    
    # 如果命令行参数提供了文件夹路径，自动加载
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        viewer.current_folder = sys.argv[1]
        viewer.load_images_from_folder(sys.argv[1])
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
