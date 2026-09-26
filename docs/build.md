# Building and releasing / 构建与发布

## 中文

Windows 下载包必须在 Windows 上构建。开发环境建议 Python 3.12：

```powershell
python -m pip install pyinstaller==6.22.3
./build_windows.ps1 -Version 0.1.0
```

构建脚本生成 `dist/business-literature-radar-v0.1.0-windows.zip`，同时打印 SHA-256。压缩包包含单文件 `BusinessLiteratureRadar.exe`、`run.bat`、双语文档、两份原生 Skill 和可跨平台使用的 Python 源码。它**不包含** `output/`、本地配置文件或作者的 API Key。若想重新构建同一版本，请明确删除旧 ZIP 后再运行；脚本不会悄悄覆盖它。

推送到 `main` 时，GitHub Actions 会做离线自检并提供临时构建产物；推送形如 `v0.1.0` 的新标签时，同一流程还会创建公开 GitHub Release 并附上 Windows ZIP。GitHub Actions 的构建环境不需要、也不应配置任何 LLM API 密钥。发布前应人工检查压缩包内容、首次启动、规则模式检索、用户 Key 设置流程与报告语言切换。

源码运行只需要 Python 3.10+ 标准库。执行以下命令进行不联网的引擎自检：

```powershell
python ./search_papers.py --self-test
```

`build_windows.ps1` 会检查源码中的绝对本机路径和旧密钥文件引用，但不能代替完整的人工检查。发布者应检查本次提交与打包内容中没有 Key、私有设置、研究数据或 `output/`。

## English

Build the Windows archive on Windows. Python 3.12 is recommended for the build:

```powershell
python -m pip install pyinstaller==6.22.3
./build_windows.ps1 -Version 0.1.0
```

The script creates `dist/business-literature-radar-v0.1.0-windows.zip` and prints its SHA-256. The archive contains the single-file `BusinessLiteratureRadar.exe`, `run.bat`, bilingual documentation, both native Skills, and the cross-platform Python source. It does **not** include `output/`, local settings, or the author's API key. To rebuild the same version, explicitly remove the previous ZIP first; the script does not silently overwrite it.

Pushing to `main` runs offline checks and produces a temporary artifact in GitHub Actions. Pushing a new tag such as `v0.1.0` additionally creates a public GitHub Release with the Windows ZIP. No LLM API secret is needed or expected in the build environment. Before publishing, manually inspect the archive and test first launch, rules-mode search, user-key setup, and report language switching.

Running from source needs only Python 3.10+ and its standard library. This engine self-test does not contact the network:

```powershell
python ./search_papers.py --self-test
```

The build script checks source for absolute local paths and an old private-key reference, but this does not replace a full human review. Check commits and the packaged contents for keys, private settings, research data, and `output/` before every release.
