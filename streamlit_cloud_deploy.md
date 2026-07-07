# Streamlit Community Cloud 部署说明

## 1. 部署前检查

确认这些文件会提交到 GitHub：

- `app.py`
- `deepseek_client.py`
- `excel_template.py`
- `ali1688_helper.py`
- `requirements.txt`
- `extensions/1688_product_exporter/`
- `docs/`

确认这些文件不要提交：

- `.env`
- `.venv/`
- `output/`

当前 `.gitignore` 已经忽略这些本地文件。

## 2. 推送到 GitHub

在项目根目录执行：

```bash
git init
git add .
git commit -m "Deploy Streamlit AliExpress listing tool"
git branch -M main
git remote add origin <你的 GitHub 仓库地址>
git push -u origin main
```

如果你已经有 Git 仓库，只需要正常 `git add`、`git commit`、`git push`。

## 3. 在 Streamlit Community Cloud 创建应用

1. 打开 https://share.streamlit.io/
2. 登录 GitHub。
3. 点击 `Create app`。
4. 选择你的仓库。
5. Branch 选择 `main`。
6. Main file path 填：

```text
app.py
```

7. 点击部署。

## 4. 配置 Secrets

在 Streamlit Cloud 应用页面进入 `Settings` -> `Secrets`，填入：

```toml
APP_PASSWORD = "换成你的访问密码"
DEEPSEEK_API_KEY = "你的 DeepSeek API Key"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DRY_RUN = "true"
```

保存后重启应用。

## 5. 访问控制

应用启动后会先显示登录页。只有输入 `APP_PASSWORD` 才能进入工具页面。

这是轻量级密码保护，适合小范围分享，不适合作为高安全等级账号系统。公开分享链接时请注意：

- DeepSeek 翻译会消耗你的 API 余额。
- 不要把 Streamlit Secrets、`.env` 或 API Key 发给别人。
- 如果要给多人长期使用，建议后续升级为用户自己的 API Key 或正式账号系统。

## 6. Chrome 插件

Streamlit Cloud 只部署网页应用，不会自动安装 Chrome 插件。

其他用户仍需要手动安装本项目里的本地插件：

```text
extensions/1688_product_exporter
```

安装方式：

1. 打开 `chrome://extensions/`
2. 打开开发者模式。
3. 点击“加载已解压的扩展程序”。
4. 选择 `extensions/1688_product_exporter`。
