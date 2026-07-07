# AliExpress Russia 官方 API 核验记录

核验日期：2026-06-23

## 官方文档 URL

1. 创建并上传商品：https://business.aliexpress.ru/zh/docs/local-create-products
2. API Token / JWT Token：https://business.aliexpress.ru/zh/docs/api-token
3. 获取类目及其属性：https://business.aliexpress.ru/docs/categories
4. 获取配送模板：https://business.aliexpress.ru/docs/local-get-shipping-templates
5. 管理商品分组：https://business.aliexpress.ru/zh/docs/product-groups

## 已核验事实

### API Base URL

官方文档写明生产环境地址：

```text
https://openapi.aliexpress.ru
```

### 认证方式

官方文档要求使用 JWT token，并在请求头中传递：

```text
x-auth-token: <YOUR_API_TOKEN>
```

部分接口还支持/要求：

```text
x-request-locale: en_US 或 ru_RU
Content-Type: application/json
accept: application/json
```

注意：官方 AliExpress Russia 文档没有使用 AliExpress 国际开放平台的 app_key/sign/session 旧认证方式，本项目也不会实现那套认证。

### 创建商品接口

```text
POST /api/v1/product/create
```

完整 URL：

```text
https://openapi.aliexpress.ru/api/v1/product/create
```

创建商品接口返回的 `group_id` 是商品上传任务批次 ID，不是商品分组 ID。官方文档明确说明可通过 `GET /api/v1/tasks?group_id=` 查询任务完成状态。

### 查询任务状态接口

创建商品文档明确引用：

```text
GET /api/v1/tasks?group_id=<group_id>
```

完整 URL：

```text
https://openapi.aliexpress.ru/api/v1/tasks?group_id=<group_id>
```

### 获取类目接口

获取顶级类目：

```text
POST /api/v1/categories/top
```

获取类目属性：

```text
POST /api/v1/categories/get
```

获取属性值字典：

```text
POST /api/v1/categories/values-dictionary
```

### 获取配送模板接口

```text
GET /api/v1/sellercenter/get-count-product-on-onboarding-template
```

响应中的配送模板 ID 字段在配送模板文档里是：

```text
data.templates[].template_id
```

创建商品文档有一处写成 `templates.templateId`，但配送模板接口响应示例和参数表使用 `template_id`。本项目 README 和代码注释以配送模板接口文档的 `template_id` 为准。

### 商品分组接口

商品分组文档使用另一组接口，例如：

```text
POST /api/v2/posting/create-product-group
POST /api/v2/posting/get-product-groups-by-seller
POST /api/v2/posting/edit-product-group
POST /api/v2/posting/delete-product-group
```

商品分组里的 `group_id` 表示商品分组标识符。它不同于 `product/create` 返回的上传任务批次 `group_id`。

## 创建商品请求头

官方创建商品示例包含：

```text
Content-Type: application/json
x-auth-token: <YOUR_API_TOKEN>
x-request-locale: en_US
```

示例中也出现过 `tr_TR`，但中文参数表建议 `en_US`。本项目默认使用 `en_US`，辅助查询页面可按需调整代码。

## 创建商品请求体核心字段

官方文档核验到的核心结构：

```json
{
  "products": [
    {
      "aliexpress_category_id": 200000361,
      "external_id": "1005006950054494",
      "attribute_list": [],
      "freight_template_id": 24117182098,
      "language": "ru",
      "main_image_urls_list": [],
      "multi_language_description_list": [],
      "multi_language_subject_list": [],
      "package_length": 30,
      "package_width": 30,
      "package_height": 5,
      "weight": "2",
      "shipping_lead_time": 5,
      "product_unit": 100000015,
      "sku_info_list": []
    }
  ]
}
```

SKU 核心字段：

```json
{
  "sku_code": "123456789",
  "price": "999999",
  "discount_price": "888888",
  "inventory": 999,
  "sku_attributes_list": []
}
```

## 必填字段

按官方创建商品文档：

- `products`：必填，商品对象数组。
- `aliexpress_category_id`：必填，必须是末级类目。
- `attribute_list`：如果该类目包含至少一个必填属性，则必填。
- `freight_template_id`：必填。
- `language`：必填。
- `main_image_urls_list`：必填，1 至 6 个直链。
- `multi_language_description_list`：必填。
- `multi_language_description_list[].language`：必填。
- `multi_language_description_list[].web`：必填。
- `multi_language_description_list[].mobile`：必填。
- `multi_language_subject_list`：必填。
- `multi_language_subject_list[].language`：必填。
- `multi_language_subject_list[].subject`：必填。
- `package_length`：必填，1 到 700 cm。
- `package_width`：必填，1 到 700 cm。
- `package_height`：必填，1 到 700 cm。
- `weight`：必填，0.01 到 700 kg，字符串。
- `product_unit`：必填。
- `shipping_lead_time`：必填，1 到 30。
- `sku_info_list`：必填。
- `sku_info_list[].sku_code`：必填。
- `sku_info_list[].price`：必填，字符串，最小值 0.01。
- `sku_info_list[].inventory`：必填，0 到 999999。
- `sku_attributes_list[].sku_attribute_name_id`：当传 SKU 属性对象时必填。
- `sku_attributes_list[].sku_attribute_value_id`：当传 SKU 属性对象时必填。

## 不确定或需要人工确认的字段

- `attribute_list` 必须根据具体末级类目的 `POST /api/v1/categories/get` 返回值人工确认，尤其是品牌、认证、材质、TNVED/OKPD2/GTIN 等类目要求。本项目不猜这些字段。
- `sku_attributes_list` 是否必填取决于具体类目的 SKU 属性规则。本项目第一版支持空数组，适合单 SKU；若类目要求规格属性，需人工填写。
- `product_unit` 可选值需从官方文档或卖家后台确认；本项目默认使用用户给定的 `100000015`，但真实发布前应人工确认。
- `language` 可选值表在页面中折叠显示，第一版默认 `ru`，真实发布前请确认目标类目/接口是否接受。
- 文档示例中出现 `hs_codes`，参数表中出现 `tnved_codes`、`gtin`、`okpd2_codes`。本项目第一版不写入这些字段，除非你人工确认类目需要。

## 关键注意事项

1. `200 OK` 不代表商品创建成功。创建商品接口可能在 `200 OK` 中返回 `results[].ok=false` 和 `errors`。
2. 必须使用 `GET /api/v1/tasks?group_id=<group_id>` 查询上传任务状态。
3. `product/create` 返回的 `group_id` 是上传任务组 ID，不是商品分组 ID。
4. 商品分组文档中的 `group_id` 属于商品分组接口，是另一种业务 ID。
5. 本项目只使用 AliExpress Russia 官方文档核验到的接口，不使用 AliExpress 国际版 API 或淘宝开放平台 API。
