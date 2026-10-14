# Video2Blockout

Turn a short video into relative depth and editable, abstract 3D blockout animation.

视频 → 相对深度 → 对象选择与追踪 → 抽象白模 → Blender 动画。

## Windows 一键使用

从 [Releases](https://github.com/jackbid211/Video2Blockout/releases) 下载 Windows 便携版，完整解压，双击 `Launch.cmd`，点击 **Start**。服务就绪后自动打开浏览器；保留启动器窗口。**Open tool** 打开工具，**Stop** 停止服务，**View logs** 查看日志。

便携版包含 Python、CPU 深度处理依赖和模型缓存，无需安装 Codex 或 Python。YOLO 自动识别依赖暂不包含；支持手动框选。Windows 10/11 x64，解压目录须可写。

## Features

- 浏览器采样短视频：最长边 640px，最多 120 帧。
- Depth Anything V2 Small 单目相对逆深度；不框选也可以只生成深度。
- 可选 COCO 预训练 YOLO11 第一帧检测，支持人、马、汽车等。
- 手动框选、CSRT 追踪、GrabCut 前景分割、保留对象选择。
- 人物、马匹、汽车、四足动物、桌子及通用几何体模板。
- WebM 预览视频、深度 / 遮罩 NPZ、项目 JSON 与 Blender 场景生成脚本。
- 处理后可点击“返回第一帧框选”，补选对象再生成白模。

## Source setup

Python 3.12 recommended:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-model.txt
.\.venv\Scripts\python.exe app.py --open-browser
```

自动识别另装 `requirements-detect.txt`。首次运行会下载模型；视频在本机处理。`Launch.cmd` 用于包含 `portable-python` 和 `runtime-packages` 的便携版，源码安装使用上面的命令。

## Workflow

1. 导入视频并提取帧。
2. 仅要深度可直接运行模型；要白模则先在原视频第一帧拖动框选，并选好几何模板。
3. 处理完成后查看深度与分割，勾选保留对象，切换抽象白模。
4. 导出 WebM，或在 Blender 文本编辑器运行导出的 `build_blockout.py` 创建新场景。

`demo-preview.html` 是无需服务的合成演示，不是上传视频的实时推理入口。真实视频处理必须使用本地服务页面。

## Validation and limitations

15 Python tests pass, including local HTTP / JavaScript routes. JavaScript loader lifecycle checks pass. A real H.264 clip was decoded into 26 frames and processed with Depth Anything; the exported depth MP4 was decoded again successfully. User footage and results are excluded from this repository.

Windows launcher syntax was checked; the complete desktop button workflow and Blender rendering have not been verified. YOLO detection has not been evaluated on real clips in this project.

相对深度不是米制距离；当前采用固定机位、正交投影近似，不恢复真实尺度、相机运动、物体背面或骨骼动作。马腿和车轮是静态模板，随整个对象移动缩放。YOLO 仅发现第一帧对象，后进入画面的对象不会自动加入。CSRT 不具备遮挡后的身份重识别；GrabCut 失败时使用矩形遮罩。白模网页视图是二维投影，Blender 导出才创建三维几何体。

## Tests

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
node tests/test_video_loader.cjs
python make_demo.py
python build_preview.py
```

## License

Project code: MIT. Third-party runtimes, libraries and model weights retain their own licenses. See the [Depth Anything V2 model card](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf) and [Ultralytics licensing](https://docs.ultralytics.com/models/yolo11/).
