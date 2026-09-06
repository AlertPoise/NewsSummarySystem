/**
 * 模型指标 ViewModel（E4-16 配套）。
 * GET /api/model/metrics 返回 B 角色交付的最新正式评价（CNewSum test）；
 * 无正式评价记录时服务端返回 404/1002，界面展示“暂无数据”而非错误。
 * 客户端不硬编码任何指标数值。
 */

import { ApiException, HttpClient } from '../common/HttpClient';
import { MetricsData } from '../model/News';

@Observed
export class MetricsViewModel {
  /** 最新正式模型评价；无记录或加载失败时为 null。 */
  metrics: MetricsData | null = null;

  /** 加载中。 */
  loading: boolean = true;

  /** 错误信息。 */
  errorMessage: string = '';

  /** 服务端明确返回“暂无正式评价记录”（404/1002）。 */
  empty: boolean = false;

  private client: HttpClient = new HttpClient();
  private inFlight: boolean = false;

  /** 拉取最新模型指标；重复调用会被 inFlight 保护。 */
  async load(): Promise<void> {
    if (this.inFlight) {
      return;
    }
    this.inFlight = true;
    if (this.metrics === null) {
      this.loading = true;
    }
    this.errorMessage = '';
    this.empty = false;
    try {
      this.metrics = await this.client.getMetrics();
    } catch (err) {
      if (err instanceof ApiException && err.code === 1002) {
        // 暂无正式评价记录：按空态展示，不与网络错误混淆（E4-18）。
        this.empty = true;
        this.metrics = null;
      } else {
        this.errorMessage = `指标加载失败：${err.message}`;
      }
    } finally {
      this.loading = false;
      this.inFlight = false;
    }
  }
}
