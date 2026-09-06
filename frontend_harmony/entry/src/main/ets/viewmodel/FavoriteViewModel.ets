/**
 * 收藏列表 ViewModel（E4-14 配套）。
 * GET /api/favorites 仅返回当前 X-Client-ID 的收藏；
 * 每次进入/被通知变化时调用 reload，界面提供下拉刷新与错误重试。
 */

import { common } from '@kit.AbilityKit';
import { ClientIdManager } from '../common/ClientIdManager';
import { HttpClient } from '../common/HttpClient';
import { NewsItem } from '../model/News';

@Observed
export class FavoriteViewModel {
  /** 当前客户端的收藏新闻列表。 */
  favorites: NewsItem[] = [];

  /** 首次加载中（列表为空时展示加载态）。 */
  loading: boolean = true;

  /** 已有数据时的刷新中状态。 */
  refreshing: boolean = false;

  /** 错误信息。 */
  errorMessage: string = '';

  private client: HttpClient = new HttpClient();
  private context: common.UIAbilityContext | null = null;
  private inFlight: boolean = false;

  /** 绑定界面上下文。 */
  attach(context: common.UIAbilityContext): void {
    this.context = context;
  }

  /** 重新拉取收藏列表；有数据时静默刷新避免闪烁。 */
  async reload(): Promise<void> {
    const ctx: common.UIAbilityContext | null = this.context;
    if (ctx === null || this.inFlight) {
      return;
    }
    this.inFlight = true;
    const hasData: boolean = this.favorites.length > 0;
    if (hasData) {
      this.refreshing = true;
    } else {
      this.loading = true;
    }
    this.errorMessage = '';
    try {
      await ClientIdManager.ensureClientId(ctx);
      const list: NewsItem[] = await this.client.getFavorites();
      this.favorites = list;
    } catch (err) {
      this.errorMessage = `收藏加载失败：${err.message}`;
    } finally {
      this.loading = false;
      this.refreshing = false;
      this.inFlight = false;
    }
  }
}
