/**
 * API 配置：后端地址与客户端公共常量（E4-02 配套）。
 * 字段与标识符使用英文；注释使用中文。
 * 所有地址/超时配置集中在此文件，页面与 ViewModel 不直接拼接后端地址。
 */

export class ApiConfig {
  /**
   * 后端 FastAPI 基础地址。
   * - HarmonyOS 模拟器访问宿主机固定使用 http://10.0.2.2:8000；
   * - 真机联调改为后端局域网 IP（如 http://192.168.1.100:8000），
   *   要求后端以 uvicorn --host 0.0.0.0 启动并放行防火墙 8000 端口（见 docs/WINDOWS_SETUP.md）。
   */
  static readonly baseUrl: string = 'http://10.0.2.2:8000';

  /** 新闻列表每页条数，遵守 API 契约 page_size 1~50 范围约束。 */
  static readonly defaultPageSize: number = 20;

  /** HTTP 连接与读取超时（毫秒）。 */
  static readonly connectTimeoutMs: number = 10000;
  static readonly readTimeoutMs: number = 20000;

  /** Preferences 存储文件名与客户端标识键名（E4-03）。 */
  static readonly prefsName: string = 'news_summary_client';
  static readonly clientIdKey: string = 'client_id';

  /** 摘要状态轮询间隔与最大次数；仅在任务已被接受（pending/processing）时有限轮询详情接口。 */
  static readonly pollIntervalMs: number = 3000;
  static readonly pollMaxTimes: number = 12;
}
