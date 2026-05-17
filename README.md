# Stock Decision System

一个面向股票研究与投资决策的多 Agent 分析工具。

项目会围绕用户输入的股票、板块或市场任务，自动收集行情与相关信息，并从多头、空头、裁判、风控和组合管理等角度生成分析结果，辅助用户更系统地判断投资机会与风险。

在线体验地址：

http://stock.supersaiyan.online/

## 项目背景

股票分析通常需要同时处理行情、宏观、公司基本面、市场情绪和风险约束等多类信息。人工整理这些信息耗时较长，也容易只看到单一角度。

本项目尝试用多 Agent 协作的方式，把一次投资分析拆成多个角色共同完成：先规划问题和数据来源，再形成多空观点、风险判断和最终决策展示。它适合用于辅助研究，不构成任何投资建议。

## 如何使用

1. 打开在线地址：http://stock.supersaiyan.online/
2. 选择运行模式：
   - 通用分析：适合分析美股、ETF 或指定股票代码。
   - 每日扫描：适合自动扫描 A 股市场机会。
   - 指定板块：适合分析某个 A 股板块。
   - 指定个股：适合深入分析指定 A 股代码。
3. 填写 OpenRouter API Key。
4. 根据模式填写股票代码、板块、风险偏好、资金规模和任务描述。
5. 点击「运行决策」，等待系统输出各阶段分析和最终结果。

常见输入示例：

```text
分析 AAPL、MSFT、NVDA 未来 1-3 个月的投资机会
```

```text
扫描全市场，找出未来 1 个月最具投资价值的 A 股标的
```

## 本地部署

### 1. 安装后端依赖

```powershell
pip install -r requirements.txt
```

### 2. 构建前端

```powershell
cd web
npm install
npm run build
cd ..
```

### 3. 启动服务

```powershell
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

启动后访问：

```text
http://127.0.0.1:8000/
```

## Docker 部署

如果使用已构建镜像，可以直接运行：

```powershell
docker compose -f docker/docker-compose.yml up -d
```

默认容器内服务端口是 `8000`，当前 compose 文件映射到宿主机：

```text
127.0.0.1:18080
```

如果需要从源码重新构建镜像，请先构建前端：

```powershell
cd web
npm install
npm run build
cd ..
```

然后构建并运行：

```powershell
docker build -t ai-stock:latest .
docker run -d --name ai-stock -p 8000:8000 ai-stock:latest
```

访问：

```text
http://127.0.0.1:8000/
```

## 配置说明

默认模型服务使用 OpenRouter。Web 页面运行时会要求填写 OpenRouter API Key；命令行或二次开发时，也可以根据需要在运行参数或环境配置中传入。

请注意：本项目输出仅用于研究和辅助分析，不代表确定收益，也不构成投资建议。
