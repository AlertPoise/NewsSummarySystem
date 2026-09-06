/**
 * 新闻详情页 ViewModel（E4-10~E4-15 配套）。
 * 负责详情拉取、AI 摘要状态展示/触发/有限轮询、全文、收藏切换与摘要反馈；
 * 详情请求始终携带已生成的 X-Client-ID（可选契约），从而返回真实收藏/反馈状态。
 * 摘要任何处理结果均来自服务端状态机（pending/processing/completed/failed），不伪造。
 */

import { common } from '@kit.AbilityKit';
import { promptAction } from '@kit.ArkUI';
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

  /** 静默刷新（不切换整页加载态）进行中，供顶部刷新按钮显示转圈。 */
  refreshingDetail: boolean = false;

  /** detail 每次替换后的通知回调（页面据此把关键状态镜像为页面级 @State）。 */
  onDetailChanged: () => void = () => {
  };

  /** 摘要任务已提交但长时间未完成时的提示（轮询超时后置位）。 */
  summaryNotice: string = '';

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
    } else {
      this.refreshingDetail = true;
    }
    this.errorMessage = '';
    try {
      await ClientIdManager.ensureClientId(ctx);
      const fresh: NewsDetail = await this.client.getNewsDetail(this.newsId);
      this.setDetail(fresh);
      if (fresh.summary_status === 'processing') {
        this.startPolling();
      } else {
        this.stopPolling();
      }
      if (fresh.summary_status !== 'pending') {
        this.summaryNotice = '';
      }
    } catch (err) {
      // 详情已存在时静默刷新失败也要让用户可见，否则“点刷新没反应”。
      const msg: string = `刷新失败：${err.message}`;
      if (full) {
        this.errorMessage = msg;
      } else {
        this.opError = msg;
      }
    } finally {
      this.refreshingDetail = false;
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
        this.summaryNotice = '';
        this.toast('摘要已生成');
      } else {
        // 202：任务被接受或仍在处理中，开始有限轮询详情直至最终状态。
        this.toast('摘要任务已提交，正在生成中…');
        this.startPolling();
      }
    } catch (err) {
      this.opError = `摘要请求失败：${err.message}`;
      this.toast('摘要请求失败，请稍后重试');
    } finally {
      this.summaryBusy = false;
      this.notifyState();
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
    this.setDetail(next);
  }

  /** 收藏/取消收藏切换（E4-13：幂等语义由服务端保证，界面以响应为准）。
   *  采用乐观更新：点击立即翻转按钮状态给出即时反馈，请求成功后以服务端结果校准，
   *  失败则回滚并提示，避免“点了没反应”。 */
  async toggleFavorite(): Promise<void> {
    const ctx: common.UIAbilityContext | null = this.context;
    const current: NewsDetail | null = this.detail;
    if (ctx === null || current === null || this.favoriteBusy) {
      return;
    }
    this.favoriteBusy = true;
    this.opError = '';
    const target: boolean = !current.is_favorite;
    const optimistic: NewsDetail = NewsDetail.copyOf(current);
    optimistic.is_favorite = target;
    this.setDetail(optimistic);
    try {
      await ClientIdManager.ensureClientId(ctx);
      const result: FavoriteOperationResult =
        target ? await this.client.addFavorite(current.id) : await this.client.removeFavorite(current.id);
      // 以服务端响应校准（基于乐观对象复制，避免 null 联合类型）。
      const next: NewsDetail = NewsDetail.copyOf(optimistic);
      next.is_favorite = result.is_favorite;
      this.setDetail(next);
      this.markFavoritesDirty();
      this.toast(result.is_favorite ? '已收藏' : '已取消收藏');
    } catch (err) {
      // 请求失败：回滚到真实状态并提示。
      const rollback: NewsDetail = NewsDetail.copyOf(optimistic);
      rollback.is_favorite = current.is_favorite;
      this.setDetail(rollback);
      this.opError = `收藏操作失败：${err.message}`;
      this.toast('操作失败，请检查网络后重试');
    } finally {
      this.favoriteBusy = false;
      this.notifyState();
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
      this.setDetail(next);
    } catch (err) {
      this.opError = `反馈提交失败：${err.message}`;
    } finally {
      this.feedbackBusy = false;
      this.notifyState();
    }
  }

  /** 清除操作错误提示。 */
  clearOpError(): void {
    this.opError = '';
  }

  /** 替换详情对象并通知页面同步镜像（页面依赖镜像字段驱动 UI 刷新）。 */
  private setDetail(next: NewsDetail): void {
    this.detail = next;
    this.onDetailChanged();
  }

  /** 不替换 detail 但通知页面重新同步镜像（如请求结束 busy 复位）。 */
  notifyState(): void {
    this.onDetailChanged();
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

  /** 单次轮询：拉取详情并按状态决定继续或停止。单次失败不中断（任务可能仍在生成）。 */
  private async pollOnce(): Promise<void> {
    this.pollTimes++;
    try {
      const fresh: NewsDetail = await this.client.getNewsDetail(this.newsId);
      this.setDetail(fresh);
      const status: string = fresh.summary_status;
      if (status === 'completed' || status === 'failed') {
        this.summaryNotice = '';
        this.stopPolling();
        this.notifyState();
        return;
      }
    } catch (err) {
      // 单次网络抖动不终止轮询：继续查直到达到次数上限，避免任务完成却错过同步。
      if (this.opError.length === 0) {
        this.opError = `状态刷新失败：${err.message}`;
      }
    } finally {
      if (this.pollTimes >= ApiConfig.pollMaxTimes) {
        this.stopPolling();
        this.notifyState();
        const current: NewsDetail | null = this.detail;
        if (current !== null && current.summary_status !== 'completed' &&
          current.summary_status !== 'failed') {
          this.summaryNotice = '摘要任务仍在服务端处理中，可稍后点击“刷新状态”查看结果';
        }
      }
    }
  }

  /** 轻量 Toast 提示（操作成功/失败/进度等即时反馈）。 */
  private toast(message: string): void {
    promptAction.showToast({ message: message, duration: 1800 });
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
