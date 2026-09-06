/**
 * 统一 HTTP 请求层（E4-02）。
 * 实现输入仅为 docs/API.md 冻结契约，不读取任何 Python 后端源码；
 * 所有路径、Header 规则、错误语义均以该契约文档为准。
 * 调用链固定为：Page/View -> ViewModel -> HttpClient -> FastAPI。
 *
 * 统一响应约定：成功 {"code":0,"message":"ok","data":...}；
 * 错误 {"code":非0,"message":"...","data":null}；HTTP 400/404/409/422/500/503。
 */

import { http } from '@kit.NetworkKit';
import { ApiConfig } from './ApiConfig';
import { ClientIdManager } from './ClientIdManager';
import { jsonArray, jsonNumber, jsonObject, jsonString } from './JsonUtil';
import {
  FeedbackResult, FavoriteOperationResult, MetricsData, NewsDetail, NewsItem, NewsPageData, SummaryTaskResult
} from '../model/News';

/** 业务异常：message 为可直接展示的中文文案（优先取服务端 message，否则按状态映射）。 */
export class ApiException extends Error {
  /** 业务错误码（1001/1002/1003/1004/1005 等，见 docs/API.md）。 */
  code: number;
  /** HTTP 状态码。 */
  httpStatus: number;

  constructor(code: number, httpStatus: number, message: string) {
    super(message);
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

/** X-Client-ID 附加策略。 */
enum ClientHeaderMode {
  /** 不附加客户端标识。 */
  None = 0,
  /** 已存在客户端标识时附加（新闻详情可选场景）。 */
  IfPresent = 1,
  /** 必须附加，缺失时报 1001（收藏/反馈等必填端点）。 */
  Required = 2
}

export class HttpClient {
  /**
   * GET /api/categories：固定六类（科技、财经、社会、体育、国内、国际），稳定顺序。
   */
  async getCategories(): Promise<string[]> {
    const wrapper: Record<string, Object> = await this.requestJson('/api/categories',
      http.RequestMethod.GET, ClientHeaderMode.None, null);
    const raw: Array<Object> | null = jsonArray(wrapper['data']);
    const categories: string[] = [];
    if (raw !== null) {
      for (let i = 0; i < raw.length; i++) {
        const item: Object = raw[i];
        if (item !== null && item !== undefined) {
          categories.push(item as string);
        }
      }
    }
    return categories;
  }

  /**
   * GET /api/news：分页查询新闻列表（不含 content）。
   * category 为空表示全部；遵守 page>=1、page_size 1~50。
   */
  async getNewsList(page: number, pageSize: number, category: string): Promise<NewsPageData> {
    let query: string = `page=${page}&page_size=${pageSize}`;
    if (category.length > 0) {
      query = `${query}&category=${encodeURIComponent(category)}`;
    }
    const wrapper: Record<string, Object> = await this.requestJson(`/api/news?${query}`,
      http.RequestMethod.GET, ClientHeaderMode.None, null);
    const data: Record<string, Object> | null = jsonObject(wrapper['data']);
    if (data === null) {
      throw new ApiException(-1, 200, '新闻列表数据为空');
    }
    return NewsPageData.fromJson(data);
  }

  /**
   * GET /api/news/{news_id}：新闻详情。
   * X-Client-ID 可选：客户端标识已存在时附加以返回收藏/反馈状态。
   */
  async getNewsDetail(newsId: number): Promise<NewsDetail> {
    const wrapper: Record<string, Object> = await this.requestJson(`/api/news/${newsId}`,
      http.RequestMethod.GET, ClientHeaderMode.IfPresent, null);
    const data: Record<string, Object> | null = jsonObject(wrapper['data']);
    if (data === null) {
      throw new ApiException(-1, 200, '新闻详情数据为空');
    }
    return NewsDetail.fromJson(data);
  }

  /**
   * POST /api/news/{news_id}/summary：发起或重试摘要任务，不执行推理。
   * 返回 200(completed) 或 202(pending/processing/failed 重置)；调用方按状态展示或轮询详情。
   */
  async requestSummary(newsId: number): Promise<SummaryTaskResult> {
    const wrapper: Record<string, Object> = await this.requestJson(`/api/news/${newsId}/summary`,
      http.RequestMethod.POST, ClientHeaderMode.None, null);
    const data: Record<string, Object> | null = jsonObject(wrapper['data']);
    if (data === null) {
      throw new ApiException(-1, 200, '摘要任务数据为空');
    }
    return SummaryTaskResult.fromJson(data);
  }

  /**
   * GET /api/favorites：当前客户端的收藏列表（X-Client-ID 必填，调用前需 ensureClientId）。
   */
  async getFavorites(): Promise<NewsItem[]> {
    const wrapper: Record<string, Object> = await this.requestJson('/api/favorites',
      http.RequestMethod.GET, ClientHeaderMode.Required, null);
    const raw: Array<Object> | null = jsonArray(wrapper['data']);
    const items: NewsItem[] = [];
    if (raw !== null) {
      for (let i = 0; i < raw.length; i++) {
        const itemJson: Record<string, Object> | null = jsonObject(raw[i]);
        if (itemJson !== null) {
          items.push(NewsItem.fromJson(itemJson));
        }
      }
    }
    return items;
  }

  /** POST /api/favorites/{news_id}：幂等收藏（X-Client-ID 必填）。 */
  async addFavorite(newsId: number): Promise<FavoriteOperationResult> {
    const wrapper: Record<string, Object> = await this.requestJson(`/api/favorites/${newsId}`,
      http.RequestMethod.POST, ClientHeaderMode.Required, null);
    const data: Record<string, Object> | null = jsonObject(wrapper['data']);
    if (data === null) {
      throw new ApiException(-1, 200, '收藏结果数据为空');
    }
    return FavoriteOperationResult.fromJson(data);
  }

  /** DELETE /api/favorites/{news_id}：幂等取消收藏（X-Client-ID 必填）。 */
  async removeFavorite(newsId: number): Promise<FavoriteOperationResult> {
    const wrapper: Record<string, Object> = await this.requestJson(`/api/favorites/${newsId}`,
      http.RequestMethod.DELETE, ClientHeaderMode.Required, null);
    const data: Record<string, Object> | null = jsonObject(wrapper['data']);
    if (data === null) {
      throw new ApiException(-1, 200, '取消收藏结果数据为空');
    }
    return FavoriteOperationResult.fromJson(data);
  }

  /** POST /api/news/{news_id}/feedback：提交摘要反馈 helpful（可重复更新，X-Client-ID 必填）。 */
  async submitFeedback(newsId: number, helpful: boolean): Promise<FeedbackResult> {
    const payload: Record<string, Object> = { 'helpful': helpful };
    const wrapper: Record<string, Object> = await this.requestJson(`/api/news/${newsId}/feedback`,
      http.RequestMethod.POST, ClientHeaderMode.Required, JSON.stringify(payload));
    const data: Record<string, Object> | null = jsonObject(wrapper['data']);
    if (data === null) {
      throw new ApiException(-1, 200, '反馈结果数据为空');
    }
    return FeedbackResult.fromJson(data);
  }

  /** GET /api/model/metrics：返回最新正式模型评价；无正式评价记录时抛 1002。 */
  async getMetrics(): Promise<MetricsData> {
    const wrapper: Record<string, Object> = await this.requestJson('/api/model/metrics',
      http.RequestMethod.GET, ClientHeaderMode.None, null);
    const data: Record<string, Object> | null = jsonObject(wrapper['data']);
    if (data === null) {
      throw new ApiException(-1, 200, '模型指标数据为空');
    }
    return MetricsData.fromJson(data);
  }

  /**
   * 统一请求入口：发起请求、超时控制、统一响应包装解析与错误映射。
   * @param path 契约路径（含 /api 前缀，可带 query）
   * @param method HTTP 方法
   * @param clientMode X-Client-ID 附加策略
   * @param body 请求体（JSON 字符串），无请求体传 null
   * @returns 解包后的 data 所属外层对象 {"code","message","data"}
   */
  private async requestJson(path: string, method: http.RequestMethod, clientMode: ClientHeaderMode,
    body: string | null): Promise<Record<string, Object>> {
    const url: string = ApiConfig.baseUrl + path;
    const headers: Record<string, string> = {};
    if (body !== null) {
      headers['Content-Type'] = 'application/json';
    }
    const clientId: string | null = ClientIdManager.getClientId();
    if (clientMode === ClientHeaderMode.Required) {
      if (clientId === null) {
        throw new ApiException(1001, 400, '客户端标识缺失，请稍后重试');
      }
      headers['X-Client-ID'] = clientId;
    } else if (clientMode === ClientHeaderMode.IfPresent && clientId !== null) {
      headers['X-Client-ID'] = clientId;
    }

    const options: http.HttpRequestOptions = {
      method: method,
      header: headers,
      connectTimeout: ApiConfig.connectTimeoutMs,
      readTimeout: ApiConfig.readTimeoutMs,
      expectDataType: http.HttpDataType.STRING
    };
    if (body !== null) {
      options.extraData = body;
    }

    const httpRequest: http.HttpRequest = http.createHttp();
    let response: http.HttpResponse;
    try {
      response = await httpRequest.request(url, options);
    } catch (err) {
      httpRequest.destroy();
      throw new ApiException(-1, 0, `无法连接服务器（错误码 ${err.code}）。请确认后端已启动且 ApiConfig.baseUrl 正确。`);
    }
    httpRequest.destroy();

    // 契约约定 expectDataType=STRING，result 直接按字符串读取
    const text: string = response.result as string;
    if (text === '') {
      throw new ApiException(-1, response.responseCode, '服务器返回空响应');
    }
    return this.unwrap(text, response.responseCode);
  }

  /** 解析统一包装并校验业务码；非 2xx 或 code!=0 时抛出 ApiException。 */
  private unwrap(text: string, statusCode: number): Record<string, Object> {
    let parsed: Object;
    try {
      parsed = JSON.parse(text);
    } catch (err) {
      throw new ApiException(-1, statusCode, `服务器响应不是合法 JSON（HTTP ${statusCode}）`);
    }
    const wrapper: Record<string, Object> | null = jsonObject(parsed);
    if (wrapper === null) {
      throw new ApiException(-1, statusCode, `服务器响应格式异常（HTTP ${statusCode}）`);
    }
    const code: number | null = jsonNumber(wrapper, 'code');
    const serverMessage: string | null = jsonString(wrapper, 'message');
    const isHttpSuccess: boolean = statusCode >= 200 && statusCode < 300;
    if (isHttpSuccess && code === 0) {
      return wrapper;
    }
    // 错误路径：优先业务码与 message，缺失时按 HTTP 状态映射契约错误。
    const errorCode: number = code !== null ? code : HttpClient.defaultErrorCode(statusCode);
    const message: string = serverMessage !== null ? serverMessage : HttpClient.defaultErrorMessage(statusCode);
    throw new ApiException(errorCode, statusCode, message);
  }

  /** 无包装字段时按 HTTP 状态映射契约错误码。 */
  private static defaultErrorCode(statusCode: number): number {
    if (statusCode === 400) {
      return 1001;
    }
    if (statusCode === 404) {
      return 1002;
    }
    if (statusCode === 409) {
      return 1003;
    }
    if (statusCode === 422) {
      return 1001;
    }
    if (statusCode === 503) {
      return 1004;
    }
    return 1005;
  }

  /** 无包装 message 时按 HTTP 状态映射可理解文案。 */
  private static defaultErrorMessage(statusCode: number): string {
    if (statusCode === 400) {
      return '请求头或参数不合法';
    }
    if (statusCode === 404) {
      return '资源不存在';
    }
    if (statusCode === 409) {
      return '状态冲突，请刷新后重试';
    }
    if (statusCode === 422) {
      return '请求参数格式错误';
    }
    if (statusCode === 503) {
      return 'AI 服务暂不可用，请稍后再试';
    }
    return `服务器内部错误（HTTP ${statusCode}）`;
  }
}
