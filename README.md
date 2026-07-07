# 1688 Product Exporter

这个 Chrome 插件用于配合本项目的 Streamlit 页面。

## 安装

1. 打开 Chrome：`chrome://extensions/`
2. 打开右上角“开发者模式”
3. 点击“加载已解压的扩展程序”
4. 选择本目录：

```text
extensions/1688_product_exporter
```

## 使用

1. 在浏览器里正常打开一个 1688 商品详情页。
2. 等页面图片和商品信息加载完成。
3. 点击插件图标。
4. 点击“导出当前 1688 商品 JSON”。
5. 下载得到 `1688_product_xxx.json`。
6. 回到 Streamlit 页面，上传这个 JSON 并点击“导入 1688 JSON”。

## 说明

插件只读取当前浏览器页面已经加载出来的 DOM 信息，不登录、不批量抓取、不绕过风控。1688 页面结构会变化，因此提取结果必须人工检查。

## 导出字段

当前 JSON 会尽量导出这些字段：

- `source`：固定为 `1688_product_exporter`
- `exported_at`：导出时间
- `url`：当前商品页链接
- `offer_id`：1688 商品 ID
- `title`：中文商品标题
- `description`：中文商品描述/参数文本
- `images`：主图/商品图，最多 6 张
- `detail_images`：详情图，最多 30 张
- `skus`：SKU/规格候选信息
- `price_ranges`：阶梯价候选信息
- `attributes`：商品属性候选信息
- `category_path`：页面类目路径候选信息
- `package`：重量和包装尺寸候选信息
