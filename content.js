(() => {
  try {
  const text = (value) => {
    if (value === null || value === undefined) return "";
    if (Array.isArray(value)) return value.map((item) => text(item)).filter(Boolean).join(", ");
    if (typeof value === "object") {
      const preferred = value.name || value.value || value.title || value.text || value.label || value.propValue;
      return preferred ? text(preferred) : "";
    }
    return String(value).replace(/\s+/g, " ").trim();
  };

  const absoluteUrl = (url) => {
    if (!url) return "";
    if (url.startsWith("//")) return `https:${url}`;
    try {
      return new URL(url, location.href).href;
    } catch {
      return "";
    }
  };

  const getMeta = (name) => {
    const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
    return text(el?.getAttribute("content"));
  };

  const decodeEscapes = (value) => {
    try {
      return JSON.parse(`"${value.replace(/"/g, '\\"')}"`);
    } catch {
      return value;
    }
  };

  const jsonishValue = (keys) => {
    const html = document.documentElement.innerHTML;
    for (const key of keys) {
      const patterns = [
        new RegExp(`"${key}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`, "i"),
        new RegExp(`'${key}'\\s*:\\s*'((?:\\\\.|[^'\\\\])*)'`, "i")
      ];
      for (const pattern of patterns) {
        const match = html.match(pattern);
        const value = text(decodeEscapes(match?.[1] || ""));
        if (value) return value;
      }
    }
    return "";
  };

  const jsonishScalarValue = (keys) => {
    const html = document.documentElement.innerHTML;
    for (const key of keys) {
      const patterns = [
        new RegExp(`"${key}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`, "i"),
        new RegExp(`'${key}'\\s*:\\s*'((?:\\\\.|[^'\\\\])*)'`, "i"),
        new RegExp(`"${key}"\\s*:\\s*(\\d+(?:\\.\\d+)?)`, "i"),
        new RegExp(`'${key}'\\s*:\\s*(\\d+(?:\\.\\d+)?)`, "i")
      ];
      for (const pattern of patterns) {
        const match = html.match(pattern);
        const value = text(decodeEscapes(match?.[1] || ""));
        if (value) return value;
      }
    }
    return "";
  };

  const extractBalancedValue = (source, startIndex) => {
    const opener = source[startIndex];
    const closer = opener === "{" ? "}" : "]";
    let depth = 0;
    let inString = false;
    let quote = "";
    let escaped = false;
    for (let index = startIndex; index < source.length; index += 1) {
      const char = source[index];
      if (inString) {
        if (escaped) {
          escaped = false;
        } else if (char === "\\") {
          escaped = true;
        } else if (char === quote) {
          inString = false;
        }
        continue;
      }
      if (char === "\"" || char === "'") {
        inString = true;
        quote = char;
      } else if (char === opener) {
        depth += 1;
      } else if (char === closer) {
        depth -= 1;
        if (depth === 0) return source.slice(startIndex, index + 1);
      }
    }
    return "";
  };

  const parseJsonLike = (value) => {
    if (!value) return null;
    const attempts = [
      value,
      value.replace(/'/g, "\""),
      value.replace(/,\s*([}\]])/g, "$1")
    ];
    for (const attempt of attempts) {
      try {
        return JSON.parse(attempt);
      } catch {
        // Continue with the next relaxed form.
      }
    }
    return null;
  };

  const embeddedJsonValue = (keys) => {
    const sources = [
      ...Array.from(document.scripts).map((script) => script.textContent || ""),
      document.documentElement.innerHTML
    ];
    for (const source of sources) {
      for (const key of keys) {
        const patterns = [
          new RegExp(`"${key}"\\s*:\\s*([\\[{])`, "i"),
          new RegExp(`'${key}'\\s*:\\s*([\\[{])`, "i"),
          new RegExp(`${key}\\s*[:=]\\s*([\\[{])`, "i")
        ];
        for (const pattern of patterns) {
          const match = pattern.exec(source);
          if (!match) continue;
          const valueStart = match.index + match[0].lastIndexOf(match[1]);
          const raw = extractBalancedValue(source, valueStart);
          const parsed = parseJsonLike(raw);
          if (parsed) return parsed;
        }
      }
    }
    return null;
  };

  const walkValues = (value, callback, state = { count: 0, limit: 2500 }) => {
    if (!value || typeof value !== "object" || state.count >= state.limit) return;
    state.count += 1;
    callback(value);
    if (Array.isArray(value)) {
      value.forEach((item) => walkValues(item, callback, state));
    } else {
      Object.values(value).forEach((item) => walkValues(item, callback, state));
    }
  };

  const firstText = (selectors) => {
    for (const selector of selectors) {
      const elements = Array.from(document.querySelectorAll(selector));
      for (const el of elements) {
        const value = text(el.innerText || el.textContent || el.getAttribute("title"));
        if (value && value.length >= 6) return value;
      }
    }
    return "";
  };

  const isVisible = (el) => {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };

  const safeVisible = (el) => {
    try {
      return isVisible(el);
    } catch {
      return true;
    }
  };

  const splitCleanLines = (value) => {
    return (value || "")
      .replace(/\u00a0/g, " ")
      .split(/[\n\r]+|(?<=。)|(?<=！)|(?<=？)|(?<=；)/)
      .map(text)
      .filter(Boolean);
  };

  const isNoiseLine = (line) => {
    if (line.length < 3) return true;
    if (/^[\d\s.,，。:：;；/\\|_-]+$/.test(line)) return true;
    if (/(登录|注册|收藏|进货单|购物车|联系客服|旺旺|店铺首页|公司档案|诚信通|举报|下载APP|手机版|扫码|关注|分享|返回顶部|广告|搜索|全部分类|首页)$/.test(line)) return true;
    if (/^(价格|起批量|成交|评价|物流|服务|支付|发货|拿样|优惠|券|¥|￥)/.test(line)) return true;
    if (line.includes("1688.com") || line.includes("阿里巴巴")) return true;
    return false;
  };

  const normalizeDescription = (value) => {
    const seen = new Set();
    const lines = [];
    for (const line of splitCleanLines(value)) {
      const normalized = text(line.replace(/^[·•\-*]\s*/, ""));
      if (isNoiseLine(normalized)) continue;
      if (seen.has(normalized)) continue;
      seen.add(normalized);
      lines.push(normalized);
      if (lines.join("\n").length > 900) break;
    }
    return lines.join("\n");
  };

  const productTextScore = (value) => {
    const clean = normalizeDescription(value);
    if (!clean) return 0;
    let score = Math.min(clean.length, 900);
    const productHits = clean.match(/(面料|材质|尺寸|尺码|颜色|款式|风格|重量|包装|规格|型号|适用|工艺|成分|袖|领|帽|拉链|印花|加绒|卫衣|外套|上衣|男女|儿童|成人|弹力|透气|厚度|产地)/g);
    const noiseHits = clean.match(/(店铺|公司|供应商|厂家|批发|诚信通|采购|客服|旺旺|发货|交易|登录|注册|收藏|首页)/g);
    score += (productHits?.length || 0) * 40;
    score -= (noiseHits?.length || 0) * 80;
    if (/[\u4e00-\u9fff]/.test(clean)) score += 80;
    if (clean.length < 30) score -= 250;
    return score;
  };

  const directChildText = (el) => {
    const parts = [];
    el.childNodes.forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        parts.push(node.textContent);
      }
    });
    return text(parts.join(" "));
  };

  const extractKeyValueText = (root) => {
    const rows = [];
    root.querySelectorAll("li, tr, dl, [class*='item'], [class*='prop'], [class*='attribute'], [class*='parameter']").forEach((el) => {
      if (!isVisible(el)) return;
      const rowText = text(el.innerText || el.textContent || "");
      if (!rowText || rowText.length > 120 || isNoiseLine(rowText)) return;
      if (/[\u4e00-\u9fff]/.test(rowText) && /[:：]/.test(rowText)) rows.push(rowText);
    });
    return rows.join("\n");
  };

  const isBadImageUrl = (url) => {
    return (
      !url ||
      !/\.(jpg|jpeg|png|webp)(\?|$)/i.test(url) ||
      /avatar|logo|icon|sprite|loading|placeholder|transparent|grey/i.test(url) ||
      /tps-\d{1,3}-\d{1,3}/i.test(url) ||
      /[-_](?:\d{1,3})x(?:\d{1,3})(?:\.|_)/i.test(url)
    );
  };

  const collectImages = (root = document) => {
    const imageItems = [];
    const seen = new Set();
    const addImage = (candidate, el, fallbackArea = 90000) => {
      const url = absoluteUrl(candidate);
      if (isBadImageUrl(url)) return;
      if (seen.has(url)) return;
      const width = el?.naturalWidth || el?.width || 0;
      const height = el?.naturalHeight || el?.height || 0;
      if ((width && width < 80) || (height && height < 80)) return;
      seen.add(url);
      imageItems.push({
        url,
        area: width && height ? width * height : fallbackArea,
        nearMain: Boolean(el?.closest?.("[class*='main'], [class*='gallery'], [class*='image'], [class*='Image'], [class*='sku']")),
        nearDetail: Boolean(el?.closest?.("#desc-lazyload-container, #detailContent, #offer-detail, #product-detail, [class*='detail'], [class*='Detail'], [class*='desc'], [class*='Desc'], [class*='rich-text'], [class*='RichText']"))
      });
    };

    root.querySelectorAll("img, source").forEach((img) => {
      const candidates = [
        img.currentSrc,
        img.src,
        img.srcset?.split(",")?.[0]?.trim()?.split(/\s+/)?.[0],
        img.getAttribute("data-src"),
        img.getAttribute("data-lazy-src"),
        img.getAttribute("data-lazyload-src"),
        img.getAttribute("data-original"),
        img.getAttribute("data-img"),
        img.getAttribute("data-url"),
        img.getAttribute("data-full")
      ];
      for (const candidate of candidates) {
        addImage(candidate, img);
      }
    });

    root.querySelectorAll("[style*='background']").forEach((el) => {
      const style = el.getAttribute("style") || "";
      const match = style.match(/url\((['"]?)(.*?)\1\)/i);
      if (match) addImage(match[2], el, 60000);
    });

    const html = document.documentElement.innerHTML;
    const imagePattern = /https?:\\?\/\\?\/[^"'\\\s<>]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"'\\\s<>]*)?/gi;
    let match;
    while ((match = imagePattern.exec(html)) !== null && imageItems.length < 120) {
      addImage(match[0].replace(/\\\//g, "/"), null, 40000);
    }
    return imageItems;
  };

  const extractOfferId = () => {
    const match = location.href.match(/\/offer\/(\d+)\.html?/);
    return match ? match[1] : "";
  };

  const cleanTitle = (value) => {
    return text(value)
      .replace(/[-_—|].*?(1688|阿里巴巴).*$/i, "")
      .replace(/批发采购.*$/i, "")
      .trim();
  };

  const isBadTitle = (value) => {
    const title = cleanTitle(value);
    if (title.length < 6) return true;
    if (/^\d+$/.test(title)) return true;
    if (/(店铺|旺铺|公司|工厂|厂家|供应商|诚信通|阿里巴巴|1688|登录|注册|首页)/.test(title)) return true;
    return false;
  };

  const extractTitle = () => {
    const candidates = [];

    const jsonTitle = jsonishValue([
      "subject",
      "offerTitle",
      "productTitle",
      "productName",
      "detailTitle",
      "title"
    ]);
    if (jsonTitle) candidates.push(jsonTitle);

    const selectors = [
      "h1",
      "[class*='offer-title']",
      "[class*='OfferTitle']",
      "[class*='product-title']",
      "[class*='ProductTitle']",
      "[class*='detail-title']",
      "[class*='DetailTitle']",
      ".title-text"
    ];
    selectors.forEach((selector) => {
      document.querySelectorAll(selector).forEach((el) => {
        candidates.push(el.innerText || el.textContent || el.getAttribute("title") || "");
      });
    });

    candidates.push(getMeta("og:title"));
    candidates.push(document.title);

    const cleaned = candidates.map(cleanTitle).filter(Boolean);
    return cleaned.find((candidate) => !isBadTitle(candidate)) || cleaned[0] || "";
  };

  const extractDescription = () => {
    const candidates = [];
    const addCandidate = (value, weight = 0) => {
      const normalized = normalizeDescription(value);
      if (normalized) {
        candidates.push({
          value: normalized,
          score: productTextScore(normalized) + weight
        });
      }
    };

    const detailSelectors = [
      "#desc-lazyload-container",
      "#detailContent",
      "#offer-detail",
      "#product-detail",
      "[class*='desc-lazyload']",
      "[class*='Desc']",
      "[class*='description']",
      "[class*='Description']",
      "[class*='detail-content']",
      "[class*='DetailContent']",
      "[class*='product-detail']",
      "[class*='ProductDetail']",
      "[class*='rich-text']",
      "[class*='RichText']",
      "[class*='attributes']",
      "[class*='Attributes']",
      "[class*='parameter']",
      "[class*='Parameter']",
      "[class*='specification']",
      "[class*='Specification']"
    ];

    detailSelectors.forEach((selector) => {
      document.querySelectorAll(selector).forEach((el) => {
        if (!isVisible(el)) return;
        const blockText = text(el.innerText || el.textContent || "");
        if (blockText.length > 20) addCandidate(blockText, 180);
        const kvText = extractKeyValueText(el);
        if (kvText) addCandidate(kvText, 260);
      });
    });

    const importantRows = [];
    document.querySelectorAll("li, tr, dl, p").forEach((el) => {
      if (!isVisible(el)) return;
      const own = text(directChildText(el) || el.innerText || el.textContent || "");
      if (own.length < 4 || own.length > 160) return;
      if (isNoiseLine(own)) return;
      if (/(面料|材质|尺寸|尺码|颜色|款式|风格|重量|包装|规格|型号|适用|工艺|成分|厚度|弹力|透气|帽|袖|领|拉链|印花|加绒)/.test(own)) {
        importantRows.push(own);
      }
    });
    if (importantRows.length) addCandidate(importantRows.join("\n"), 320);

    addCandidate(jsonishValue(["shortDescription", "detailDescription", "description"]), 80);
    addCandidate(jsonishValue(["desc"]), 30);
    addCandidate(getMeta("description"), -120);
    addCandidate(getMeta("og:description"), -120);

    candidates.sort((a, b) => b.score - a.score);
    return candidates[0]?.value || "";
  };

  const extractImages = () => {
    return collectImages()
      .sort((a, b) => Number(b.nearMain) - Number(a.nearMain) || b.area - a.area)
      .map((item) => item.url)
      .slice(0, 6);
  };

  const extractDetailImages = (mainImages) => {
    const mainSet = new Set(mainImages);
    const detailImages = collectImages()
      .filter((item) => item.nearDetail || !item.nearMain)
      .sort((a, b) => Number(b.nearDetail) - Number(a.nearDetail) || b.area - a.area)
      .map((item) => item.url)
      .filter((url, index, urls) => !mainSet.has(url) && urls.indexOf(url) === index);
    return detailImages.slice(0, 30);
  };

  const parseQuantity = (value) => {
    const match = String(value || "").match(/\d+/);
    return match ? Number(match[0]) : "";
  };

  const parsePrice = (value) => {
    const match = String(value || "").replace(/,/g, "").match(/\d+(?:\.\d+)?/);
    return match ? match[0] : "";
  };

  const extractPriceRanges = (pageText) => {
    const ranges = [];
    const seen = new Set();
    const addRange = (minQuantity, priceCny) => {
      const quantity = parseQuantity(minQuantity);
      const price = parsePrice(priceCny);
      if (!price) return;
      const key = `${quantity || ""}|${price}`;
      if (seen.has(key)) return;
      seen.add(key);
      ranges.push({ min_quantity: quantity, price_cny: price });
    };

    const priceData = embeddedJsonValue([
      "priceRange",
      "priceRanges",
      "priceRangeList",
      "ladderPrice",
      "ladderPriceList",
      "priceList",
      "priceModel",
      "priceInfo",
      "skuPriceMap"
    ]);
    walkValues(priceData, (item) => {
      if (Array.isArray(item)) return;
      const price =
        item.price ||
        item.priceCny ||
        item.offerPrice ||
        item.discountPrice ||
        item.salePrice ||
        item.skuPrice ||
        item.retailPrice ||
        item.priceDisplay ||
        item.priceText ||
        item.value;
      const quantity =
        item.startQuantity ||
        item.beginAmount ||
        item.minQuantity ||
        item.minimum ||
        item.amount ||
        item.quantity ||
        item.count;
      if (price) addRange(quantity, price);
    });

    const scalarPrice = jsonishScalarValue([
      "price",
      "salePrice",
      "offerPrice",
      "discountPrice",
      "skuPrice",
      "retailPrice",
      "minPrice",
      "maxPrice",
      "priceDisplay",
      "priceText"
    ]);
    if (scalarPrice) addRange("", scalarPrice);

    document.querySelectorAll("[class*='price'], [class*='Price'], [class*='amount'], [class*='Amount'], [class*='ladder'], [class*='Ladder']").forEach((el) => {
      if (!safeVisible(el)) return;
      const value = text(el.innerText || el.textContent || "");
      if (!value || value.length > 200) return;
      const quantityMatch = value.match(/(\d+)\s*(?:件|个|套|条|起)/);
      const priceMatch = value.match(/[¥￥]\s*(\d+(?:\.\d+)?)/) || value.match(/(\d+(?:\.\d+)?)\s*(?:元|CNY|RMB)/i);
      if (priceMatch) addRange(quantityMatch?.[1] || "", priceMatch[1]);
    });

    const rowPattern = /(\d+)\s*(?:件|个|套|条|起)?[^¥￥\d]{0,16}[¥￥]\s*(\d+(?:\.\d+)?)/g;
    let match;
    while ((match = rowPattern.exec(pageText)) !== null && ranges.length < 10) {
      addRange(match[1], match[2]);
    }
    const singlePricePattern = /[¥￥]\s*(\d+(?:\.\d+)?)/g;
    while ((match = singlePricePattern.exec(pageText)) !== null && ranges.length < 10) {
      addRange("", match[1]);
    }
    return ranges.slice(0, 10);
  };

  const extractAttributes = (description) => {
    const attributes = [];
    const seen = new Set();
    const addAttribute = (name, value) => {
      const cleanName = text(name).replace(/[：:]+$/, "");
      const cleanValue = text(value);
      if (!cleanName || !cleanValue) return;
      if (cleanName.length > 30 || cleanValue.length > 160) return;
      if (isNoiseLine(cleanName) || isNoiseLine(cleanValue)) return;
      const key = `${cleanName}|${cleanValue}`;
      if (seen.has(key)) return;
      seen.add(key);
      attributes.push({ name: cleanName, value: cleanValue });
    };

    const attributeData = embeddedJsonValue(["attributes", "productAttributes", "props", "productProps", "skuProps"]);
    walkValues(attributeData, (item) => {
      if (Array.isArray(item)) return;
      const name = item.name || item.propName || item.attributeName || item.key || item.attrName;
      const value = item.value || item.propValue || item.attributeValue || item.values || item.attrValue;
      if (Array.isArray(value)) {
        addAttribute(name, value.map((entry) => entry.name || entry.value || entry).join(", "));
      } else if (name && value) {
        addAttribute(name, value);
      }
    });

    document.querySelectorAll("li, tr, dl, [class*='attribute'], [class*='Attribute'], [class*='parameter'], [class*='Parameter'], [class*='prop'], [class*='Prop']").forEach((el) => {
      if (!isVisible(el)) return;
      const rowText = text(el.innerText || el.textContent || "");
      if (!rowText || rowText.length > 180 || !/[:：]/.test(rowText)) return;
      const [name, ...rest] = rowText.split(/[:：]/);
      addAttribute(name, rest.join(":"));
    });

    splitCleanLines(description).forEach((line) => {
      if (!/[:：]/.test(line)) return;
      const [name, ...rest] = line.split(/[:：]/);
      addAttribute(name, rest.join(":"));
    });

    return attributes.slice(0, 80);
  };

  const extractCategoryPath = () => {
    const candidates = [];
    const add = (value) => {
      const clean = text(value).replace(/^当前位置[:：]?/, "");
      if (!clean || isNoiseLine(clean)) return;
      candidates.push(clean);
    };

    document.querySelectorAll("nav a, [class*='breadcrumb'] a, [class*='Breadcrumb'] a, [class*='crumb'] a, [class*='Crumb'] a, [class*='category'] a, [class*='Category'] a").forEach((el) => {
      if (isVisible(el)) add(el.innerText || el.textContent);
    });

    const categoryData = embeddedJsonValue(["categoryPath", "catPath", "categoryNamePath", "breadcrumb", "breadcrumbs"]);
    walkValues(categoryData, (item) => {
      if (Array.isArray(item)) return;
      add(item.name || item.title || item.categoryName || item.catName || item.value);
    });

    return candidates
      .map((item) => item.split(/\s*[>＞/]\s*/))
      .flat()
      .map(text)
      .filter((item, index, items) => item && !isNoiseLine(item) && items.indexOf(item) === index)
      .slice(0, 12);
  };

  const extractSkus = () => {
    const skus = [];
    const seen = new Set();
    const addSku = (sku) => {
      const normalized = {};
      const props = sku.props || sku.attributes || sku.specs || {};
      const price =
        sku.price ||
        sku.priceCny ||
        sku.offerPrice ||
        sku.discountPrice ||
        sku.salePrice ||
        sku.skuPrice ||
        sku.retailPrice ||
        sku.priceDisplay ||
        sku.priceText;
      const stock = sku.stock || sku.canBookCount || sku.quantity || sku.amountOnSale || sku.inventory;
      const skuId = sku.skuId || sku.id || sku.skuID || sku.specId || "";
      if (Array.isArray(props)) {
        normalized.props = props.map((prop) => ({
          name: text(prop.name || prop.propName || prop.key || ""),
          value: text(prop.value || prop.propValue || prop.name || "")
        })).filter((prop) => prop.name || prop.value);
      } else {
        normalized.props = Object.fromEntries(Object.entries(props).map(([key, value]) => [key, text(value)]));
      }
      normalized.sku_id = text(skuId);
      if (price) normalized.price_cny = parsePrice(price);
      if (stock !== undefined && stock !== null && stock !== "") normalized.stock = parseQuantity(stock);
      const key = JSON.stringify(normalized);
      if (seen.has(key)) return;
      if (!normalized.sku_id && !normalized.price_cny && Object.keys(normalized.props || {}).length === 0) return;
      seen.add(key);
      skus.push(normalized);
    };

    const skuData = embeddedJsonValue(["skuMap", "skuInfoMap", "skuInfos", "skuList", "skuProps", "skuModel"]);
    walkValues(skuData, (item) => {
      if (Array.isArray(item)) return;
      if (
        item.skuId ||
        item.skuID ||
        item.specId ||
        item.price ||
        item.priceCny ||
        item.offerPrice ||
        item.stock ||
        item.canBookCount ||
        item.skuAttributes ||
        item.attributes ||
        item.props
      ) {
        addSku({
          skuId: item.skuId || item.skuID || item.specId,
          price:
            item.price ||
            item.priceCny ||
            item.offerPrice ||
            item.discountPrice ||
            item.salePrice ||
            item.skuPrice ||
            item.retailPrice ||
            item.priceDisplay ||
            item.priceText,
          stock: item.stock || item.canBookCount || item.quantity || item.inventory,
          props: item.skuAttributes || item.attributes || item.props || item.specAttrs || {}
        });
      }
    });

    document.querySelectorAll("[class*='sku'], [class*='Sku'], [class*='spec'], [class*='Spec']").forEach((root) => {
      if (!isVisible(root)) return;
      const labels = [];
      root.querySelectorAll("button, a, span, li, div").forEach((el) => {
        const value = text(el.innerText || el.textContent || el.getAttribute("title"));
        if (value && value.length <= 50 && !isNoiseLine(value)) labels.push(value);
      });
      [...new Set(labels)].slice(0, 80).forEach((value) => addSku({ props: { option: value } }));
    });

    return skus.slice(0, 120);
  };

  const parseWeight = (pageText) => {
    const match = pageText.match(/(?:包装重量|毛重|重量|净重|商品重量|产品重量)[：:\s]*([0-9]+(?:\.[0-9]+)?)\s*(kg|KG|千克|公斤|g|克)/);
    if (!match) return "";
    const value = Number(match[1]);
    const unit = match[2].toLowerCase();
    if (!Number.isFinite(value)) return "";
    if (unit === "g" || unit === "克") return String(value / 1000);
    return String(value);
  };

  const parseDimensions = (pageText) => {
    const direct = pageText.match(/(?:包装尺寸|尺寸|规格|商品尺寸|产品尺寸)[：:\s]*([0-9]+)\s*[xX*×]\s*([0-9]+)\s*[xX*×]\s*([0-9]+)\s*(cm|厘米)?/);
    if (direct) {
      return {
        length_cm: Number(direct[1]),
        width_cm: Number(direct[2]),
        height_cm: Number(direct[3])
      };
    }
    const named = pageText.match(/长[：:\s]*([0-9]+)\s*(?:cm|厘米).*?宽[：:\s]*([0-9]+)\s*(?:cm|厘米).*?高[：:\s]*([0-9]+)\s*(?:cm|厘米)/);
    if (named) {
      return {
        length_cm: Number(named[1]),
        width_cm: Number(named[2]),
        height_cm: Number(named[3])
      };
    }
    return {};
  };

  const pageText = text(document.body.innerText);
  const title = extractTitle();
  const description = extractDescription();
  const images = extractImages();
  const detailImages = extractDetailImages(images);
  const attributes = extractAttributes(description);
  const categoryPath = extractCategoryPath();
  const priceRanges = extractPriceRanges(pageText);
  const skus = extractSkus();
  const packageInfo = {
    weight_kg: parseWeight(pageText),
    ...parseDimensions(pageText)
  };

  if (!title && images.length === 0 && !extractOfferId()) {
    return {
      ok: false,
      error: "没有从当前页面 DOM 中识别到标题或图片。请确认 1688 商品页已完全加载。"
    };
  }

  return {
    ok: true,
    data: {
      source: "1688_product_exporter",
      exported_at: new Date().toISOString(),
      url: location.href,
      offer_id: extractOfferId(),
      title,
      description,
      images,
      detail_images: detailImages,
      skus,
      price_ranges: priceRanges,
      attributes,
      category_path: categoryPath,
      package: packageInfo,
      diagnostics: {
        title_found: Boolean(title),
        main_image_count: images.length,
        detail_image_count: detailImages.length,
        sku_count: skus.length,
        attribute_count: attributes.length,
        price_range_count: priceRanges.length,
        page_text_length: pageText.length
      }
    }
  };
  } catch (error) {
    return {
      ok: false,
      error: `插件运行出错：${error.message}`,
      stack: error.stack
    };
  }
})();
