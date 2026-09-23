# Render 一键部署指南

本项目已配置好 `render.yaml`（Blueprint），在 Render 上连接 GitHub 后会自动识别，无需手动填 Build/Start 命令。

## 前置：把代码推到 GitHub

1. 手机浏览器打开 https://github.com/new
2. 新建仓库（如 `smart-trader-web`），Public，不要勾选 README
3. 点 "uploading an existing file"
4. 把解压后的**整个项目文件夹内容**拖进去（根目录应看到 `render.yaml`、`requirements.txt`、`backend/`、`web/`）
5. 点 "Commit changes"

## 在 Render 部署

1. 打开 https://dashboard.render.com → 注册/登录（可用 GitHub 账号一键登录）
2. 右上角 **New +** → **Web Service**
3. 选 "Deploy an existing from Git repo" → 授权 GitHub → 选你刚建的仓库
4. Render 会**自动识别 `render.yaml`**，显示服务名、新加坡节点、免费方案
5. 点 **Deploy Web Service**

## 等待构建（约 3–6 分钟）

- Building → Installing dependencies → Started
- 完成后给你地址：`https://smart-trader-web.onrender.com`（或你的服务名）
- 打开即是完整工作台

## 免费版注意事项

| 事项 | 说明 |
|---|---|
| 休眠 | 15 分钟无访问自动休眠，下次打开冷启动约 30–60 秒 |
| 磁盘 | 免费层磁盘临时，**重启后分析反馈链/审计记录会重置**（行情本身实时拉取，不影响使用） |
| 国内访问 | Render 新加坡节点，国内浏览器打开速度一般；稳定访问建议套 Cloudflare 或用 Zeabur |
| 数据源 | 部署到 Render 后服务器在海外，币安/Gate/OKX/Yahoo 行情**全部可达**（比本地受限网络更好） |

## 本地开发（可选）

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
