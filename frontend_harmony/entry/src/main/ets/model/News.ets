/**
 * 数据模型（E4-04：字段名与 docs/API.md 冻结 JSON 保持一致）。
 * 服务端时间字段为 ISO 8601 字符串，本地直接保存字符串用于展示格式化。
 * 解析函数按字段读取 JSON；可空字段缺失或为 null 时保持默认值。
 */

import {
  jsonArray, jsonBool, jsonBoolDef, jsonNumber, jsonNumberDef, jsonObject, jsonString, jsonStringDef
} from '../common/JsonUtil';

/** 新闻列表单项（不含 content），与 GET /api/news、GET /api/favorites 单项一致。 */
export class NewsItem {
  id: number = 0;
  title: string = '';
  summary: string | null = null;
  category: string = '';
  source: string = '';
  publish_time: string | null = null;
  summary_status: string = '';

  /** 从 JSON 对象解析列表单项。 */
  static fromJson(json: Record<string, Object>): NewsItem {
    const item: NewsItem = new NewsItem();
    item.id = jsonNumberDef(json, 'id', 0);
    item.title = jsonStringDef(json, 'title', '');
    item.summary = jsonString(json, 'summary');
    item.category = jsonStringDef(json, 'category', '');
    item.source = jsonStringDef(json, 'source', '');
    item.publish_time = jsonString(json, 'publish_time');
    item.summary_status = jsonStringDef(json, 'summary_status', '');
    return item;
  }
}

/** 新闻详情（含 content 与用户状态），对应 GET /api/news/{news_id}。 */
export class NewsDetail {
  id: number = 0;
  title: string = '';
  content: string = '';
  summary: string | null = null;
  category: string = '';
  source: string = '';
  source_url: string = '';
  publish_time: string | null = null;
  summary_status: string = '';
  summary_time_ms: number | null = null;
  is_favorite: boolean = false;
  feedback: boolean | null = null;

  /** 从 JSON 对象解析新闻详情。 */
  static fromJson(json: Record<string, Object>): NewsDetail {
    const detail: NewsDetail = new NewsDetail();
    detail.id = jsonNumberDef(json, 'id', 0);
    detail.title = jsonStringDef(json, 'title', '');
    detail.content = jsonStringDef(json, 'content', '');
    detail.summary = jsonString(json, 'summary');
    detail.category = jsonStringDef(json, 'category', '');
    detail.source = jsonStringDef(json, 'source', '');
    detail.source_url = jsonStringDef(json, 'source_url', '');
    detail.publish_time = jsonString(json, 'publish_time');
    detail.summary_status = jsonStringDef(json, 'summary_status', '');
    detail.summary_time_ms = jsonNumber(json, 'summary_time_ms');
    detail.is_favorite = jsonBoolDef(json, 'is_favorite', false);
    detail.feedback = jsonBool(json, 'feedback');
    return detail;
  }

  /** 复制详情对象：用于收藏/反馈等局部更新后生成新对象触发界面刷新。 */
  static copyOf(source: NewsDetail): NewsDetail {
    const copy: NewsDetail = new NewsDetail();
    copy.id = source.id;
    copy.title = source.title;
    copy.content = source.content;
    copy.summary = source.summary;
    copy.category = source.category;
    copy.source = source.source;
    copy.source_url = source.source_url;
    copy.publish_time = source.publish_time;
    copy.summary_status = source.summary_status;
    copy.summary_time_ms = source.summary_time_ms;
    copy.is_favorite = source.is_favorite;
    copy.feedback = source.feedback;
    return copy;
  }
}

/** 分页响应体，对应 GET /api/news 的 data 对象。 */
export class NewsPageData {
  items: NewsItem[] = [];
  page: number = 1;
  page_size: number = 0;
  total: number = 0;

  /** 从 JSON 对象解析分页数据。 */
  static fromJson(json: Record<string, Object>): NewsPageData {
    const data: NewsPageData = new NewsPageData();
    data.page = jsonNumberDef(json, 'page', 1);
    data.page_size = jsonNumberDef(json, 'page_size', 0);
    data.total = jsonNumberDef(json, 'total', 0);
    const rawItems: Array<Object> | null = jsonArray(json['items']);
    if (rawItems !== null) {
      for (let i = 0; i < rawItems.length; i++) {
        const itemJson: Record<string, Object> | null = jsonObject(rawItems[i]);
        if (itemJson !== null) {
          data.items.push(NewsItem.fromJson(itemJson));
        }
      }
    }
    return data;
  }
}

/** 摘要任务结果，对应 POST /api/news/{news_id}/summary 的 data 对象。 */
export class SummaryTaskResult {
  news_id: number = 0;
  summary_status: string = '';
  summary: string | null = null;
  generation_time_ms: number | null = null;

  /** 从 JSON 对象解析摘要任务结果。 */
  static fromJson(json: Record<string, Object>): SummaryTaskResult {
    const result: SummaryTaskResult = new SummaryTaskResult();
    result.news_id = jsonNumberDef(json, 'news_id', 0);
    result.summary_status = jsonStringDef(json, 'summary_status', '');
    result.summary = jsonString(json, 'summary');
    result.generation_time_ms = jsonNumber(json, 'generation_time_ms');
    return result;
  }
}

/** 收藏操作结果，对应 POST/DELETE /api/favorites/{news_id} 的 data 对象。 */
export class FavoriteOperationResult {
  news_id: number = 0;
  is_favorite: boolean = false;

  /** 从 JSON 对象解析收藏操作结果。 */
  static fromJson(json: Record<string, Object>): FavoriteOperationResult {
    const result: FavoriteOperationResult = new FavoriteOperationResult();
    result.news_id = jsonNumberDef(json, 'news_id', 0);
    result.is_favorite = jsonBoolDef(json, 'is_favorite', false);
    return result;
  }
}

/** 摘要反馈结果，对应 POST /api/news/{news_id}/feedback 的 data 对象。 */
export class FeedbackResult {
  news_id: number = 0;
  helpful: boolean = false;

  /** 从 JSON 对象解析反馈结果。 */
  static fromJson(json: Record<string, Object>): FeedbackResult {
    const result: FeedbackResult = new FeedbackResult();
    result.news_id = jsonNumberDef(json, 'news_id', 0);
    result.helpful = jsonBoolDef(json, 'helpful', false);
    return result;
  }
}

/** 模型评价指标，对应 GET /api/model/metrics 的 data 对象（B 交付的正式评价结果）。 */
export class MetricsData {
  model_name: string = '';
  model_version: string = '';
  dataset: string = '';
  dataset_split: string = '';
  sample_count: number = 0;
  rouge1: number = 0;
  rouge2: number = 0;
  rougeL: number = 0;
  avg_generation_time_ms: number = 0;
  p95_generation_time_ms: number = 0;

  /** 从 JSON 对象解析模型评价指标。 */
  static fromJson(json: Record<string, Object>): MetricsData {
    const data: MetricsData = new MetricsData();
    data.model_name = jsonStringDef(json, 'model_name', '');
    data.model_version = jsonStringDef(json, 'model_version', '');
    data.dataset = jsonStringDef(json, 'dataset', '');
    data.dataset_split = jsonStringDef(json, 'dataset_split', '');
    data.sample_count = jsonNumberDef(json, 'sample_count', 0);
    data.rouge1 = jsonNumberDef(json, 'rouge1', 0);
    data.rouge2 = jsonNumberDef(json, 'rouge2', 0);
    data.rougeL = jsonNumberDef(json, 'rougeL', 0);
    data.avg_generation_time_ms = jsonNumberDef(json, 'avg_generation_time_ms', 0);
    data.p95_generation_time_ms = jsonNumberDef(json, 'p95_generation_time_ms', 0);
    return data;
  }
}
