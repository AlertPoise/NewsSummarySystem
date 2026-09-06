/**
 * 新闻详情页 ViewModel（E4-10~E4-15 配套）。
 * 负责详情拉取、AI 摘要状态展示/触发/有限轮询、全文、收藏切换与摘要反馈；
 * 详情请求始终携带已生成的 X-Client-ID（可选契约），从而返回真实收藏/反馈状态。
 * 摘要任何处理结果均来自服务端状态机（pending/processing/completed/failed），不伪造。
 */

import { common } from '@kit.AbilityKit';
import { ApiConfig } from '../common/ApiConfig';
import { ClientIdManager } from '../common/ClientIdManager';
import { HttpClient } from '../common/HttpClient';
import { FeedbackResult, FavoriteOperationResult, NewsDetail, SummaryTaskResult } from '../model/News';

@Observed
export class NewsDetailViewModel {
  /** 新闻详情数据；加载成功前为 null。 */
  detail: NewsDetail | null = null;

  /** 当前新闻 ID。 */
  newsId: number = 0;

  /** 整页加载中（详情尚未就绪）。 */
  loading: boolean = true;

  /** 整页错误信息（加载失败）。 */
  errorMessage: string = '';

  /** 操作错误信息（收藏/反馈/摘要请求失败），成功后清空。 */
  opError: string = '';

  /** 摘要生成请求（POST /summary）进行中。 */
  summaryBusy: boolean = false;

  /** 有限轮询详情接口进行中。 */
  polling: boolean = false;

  /** 收藏切换请求进行中。 */
  favoriteBusy: boolean = false;

  /** 反馈提交进行中。 */
  feedbackBusy: boolean = false;

  private client: HttpClient = new HttpClient();
  private context: common.UIAbilityContext | null = null;
  private timerId: number = -1;
  private pollTimes: number = 0;

  /** 绑定界面上下文（用于 Preferences 等系统能力）。 */
  attach(context: common.UIAbilityContext): void {
    this.context = context;
  }

  /** 首次加载详情（整页加载态）。 */
  async load(newsId: number): Promise<void> {
    this.newsId = newsId;
    this.stopPolling();
    await this.doReload(true);
  }

  /** 整页重试（错误态重试按钮）。 */
  async retry(): Promise<void> {
    await this.doReload(true);
  }

  /** 静默刷新详情（保留当前展示，不切换加载态）。 */
  async refreshDetail(): Promise<void> {
    await this.doReload(false);
  }

  /** 拉取详情；full=true 时展示整页加载态。 */
  private async doReload(full: boolean): Promise<void> {
    const ctx: common.UIAbilityContext | null = this.context;
    if (ctx === null) {
      this.loading = false;
      this.errorMessage = '界面上下文未就绪，请返回后重试';
      return;
    }
    if (full) {
      this.loading = true;
    }
    this.errorMessage = '';
    try {
      await ClientIdManager.ensureClientId(ctx);
      const fresh: NewsDetail = await this.client.getNewsDetail(this.newsId);
      this.detail = fresh;
      if (fresh.summary_status === 'processing') {
        this.startPolling();
      }
    } catch (err) {
      this.errorMessage = err.message;
    } finally {
      if (full) {
        this.loading = false;
      }
    }
  }

  /** 触发摘要任务（E4-11：按状态机语义处理 200/202 返回，不伪造结果）。 */
  async requestSummary(): Promise<void> {
    if (this.summaryBusy) {
      return;
    }
    this.summaryBusy = true;
    this.opError = '';
    try {
      const result: SummaryTaskResult = await this.client.requestSummary(this.newsId);
      if (result.summary_status === 'completed' && result.summary !== null) {
        this.applySummary(result);
        this.stopPolling();
      } else {
        // 202：任务被接受或仍在处理中，开始有限轮询详情直至最终状态。
        this.startPolling();
      }
    } catch (err) {
      this.opError = `摘要请求失败：${err.message}`;
    } finally {
      this.summaryBusy = false;
    }
  }

  /** 用任务结果刷新详情局部字段（重新赋值对象以触发界面刷新）。 */
  private applySummary(result: SummaryTaskResult): void {
    const current: NewsDetail | null = this.detail;
    if (current === null) {
      return;
    }
    const next: NewsDetail = NewsDetail.copyOf(current);
    next.summary_status = result.summary_status;
    next.summary = result.summary;
    next.summary_time_ms = result.generation_time_ms;
    this.detail = next;
  }

  /** 收藏/取消收藏切换（E4-13：幂等语义由服务端保证，界面以响应为准）。 */
  async toggleFavorite(): Promise<void> {
    const ctx: common.UIAbilityContext | null = this.context;
    const current: NewsDetail | null = this.detail;
    if (ctx === null || current === null || this.favoriteBusy) {
      return;
    }
    this.favoriteBusy = true;
    this.opError = '';
    try {
      await ClientIdManager.ensureClientId(ctx);
      const result: FavoriteOperationResult =
        current.is_favorite ? await this.client.removeFavorite(current.id) : await this.client.addFavorite(current.id);
      const next: NewsDetail = NewsDetail.copyOf(current);
      next.is_favorite = result.is_favorite;
      this.detail = next;
      this.markFavoritesDirty();
    } catch (err) {
      this.opError = `收藏操作失败：${err.message}`;
    } finally {
      this.favoriteBusy = false;
    }
  }

  /** 提交摘要反馈（E4-15：同一 client/news 重复提交即更新当前评价）。 */
  async submitFeedback(helpful: boolean): Promise<void> {
    const ctx: common.UIAbilityContext | null = this.context;
    const current: NewsDetail | null = this.detail;
    if (ctx === null || current === null || this.feedbackBusy) {
      return;
    }
    this.feedbackBusy = true;
    this.opError = '';
    try {
      await ClientIdManager.ensureClientId(ctx);
      const result: FeedbackResult = await this.client.submitFeedback(current.id, helpful);
      const next: NewsDetail = NewsDetail.copyOf(current);
      next.feedback = result.helpful;
      this.detail = next;
    } catch (err) {
      this.opError = `反馈提交失败：${err.message}`;
    } finally {
      this.feedbackBusy = false;
    }
  }

  /** 清除操作错误提示。 */
  clearOpError(): void {
    this.opError = '';
  }

  /** 详情页销毁前停止轮询。 */
  destroy(): void {
    this.stopPolling();
  }

  /** 是否正处于摘要生成中（请求中或轮询中），供界面文案使用。 */
  isSummaryInProgress(): boolean {
    return this.summaryBusy || this.polling;
  }

  /** 摘要仍在处理时有限轮询详情接口。 */
  private startPolling(): void {
    if (this.polling) {
      return;
    }
    this.polling = true;
    this.pollTimes = 0;
    this.timerId = setInterval(() => {
      this.pollOnce();
    }, ApiConfig.pollIntervalMs);
  }

  /** 单次轮询：拉取详情并按状态决定继续或停止。 */
  private async pollOnce(): Promise<void> {
    this.pollTimes++;
    try {
      const fresh: NewsDetail = await this.client.getNewsDetail(this.newsId);
      this.detail = fresh;
      const status: string = fresh.summary_status;
      if (status === 'completed' || status === 'failed') {
        this.stopPolling();
        return;
      }
      if (this.pollTimes >= ApiConfig.pollMaxTimes) {
        this.stopPolling();
      }
    } catch (err) {
      this.opError = `状态刷新失败：${err.message}`;
      this.stopPolling();
    }
  }

  /** 停止轮询并复位计时器。 */
  private stopPolling(): void {
    if (this.timerId !== -1) {
      clearInterval(this.timerId);
      this.timerId = -1;
    }
    this.polling = false;
  }

  /** 收藏集合发生变化：通知收藏页下次可见时刷新（AppStorage 版本号递增）。 */
  private markFavoritesDirty(): void {
    let current: number = 0;
    const stored: number | undefined = AppStorage.get<number>('favoritesDirty');
    if (stored !== undefined) {
      current = stored;
    }
    AppStorage.setOrCreate<number>('favoritesDirty', current + 1);
  }
}
